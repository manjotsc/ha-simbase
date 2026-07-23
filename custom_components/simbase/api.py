"""Simbase API client."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientResponseError

from .const import (
    API_BASE_URL,
    API_ENDPOINT_SIMCARDS,
    API_ENDPOINT_USAGE,
    API_ENDPOINT_BALANCE,
    API_ENDPOINT_PLANS,
    UNSET,
)

_LOGGER = logging.getLogger(__name__)

class SimbaseApiError(Exception):
    """Base exception for Simbase API errors."""


class SimbaseAuthError(SimbaseApiError):
    """Authentication error."""


class SimbaseRateLimitError(SimbaseApiError):
    """Rate limit exceeded."""


class SimbaseApiClient:
    """Simbase API client."""

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self._api_key = api_key
        self._session = session
        self._own_session = False

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._own_session and self._session:
            await self._session.close()
            self._session = None

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an API request."""
        session = await self._get_session()
        url = f"{API_BASE_URL}{endpoint}"

        _LOGGER.debug("Making %s request to %s with params=%s", method, url, params)

        try:
            async with session.request(
                method,
                url,
                headers=self._get_headers(),
                params=params,
                json=json_data,
            ) as response:
                _LOGGER.debug("Response status: %s", response.status)

                if response.status == 401:
                    raise SimbaseAuthError("Invalid API key")
                if response.status == 429:
                    raise SimbaseRateLimitError("API rate limit exceeded")

                response.raise_for_status()
                data = await response.json()
                _LOGGER.debug("Response data: %s", data)
                return data
        except ClientResponseError as err:
            # Only log as error for non-404 responses (404 may be expected for some endpoints)
            if err.status == 404:
                _LOGGER.debug("API endpoint not found: %s", err)
            else:
                _LOGGER.error("API request failed: %s", err)
            raise SimbaseApiError(f"API request failed: {err}") from err
        except ClientError as err:
            _LOGGER.error("Connection error: %s", err)
            raise SimbaseApiError(f"Connection error: {err}") from err

    async def validate_api_key(self) -> bool:
        """Validate the API key by making a test request."""
        try:
            await self.get_simcards(limit=1)
            return True
        except SimbaseAuthError:
            return False
        except SimbaseApiError:
            # Other errors might still mean the key is valid
            return True

    async def get_simcards(
        self,
        cursor: str | None = None,
        limit: int = 100,
        state: str | None = None,
        coverage: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get list of SIM cards, optionally filtered by state/coverage/tags."""
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if state:
            params["state"] = state
        if coverage:
            params["coverage"] = coverage
        if tags:
            params["tags"] = tags
        return await self._request("GET", API_ENDPOINT_SIMCARDS, params=params)

    async def get_all_simcards(self) -> list[dict[str, Any]]:
        """Get all SIM cards with pagination."""
        simcards = []
        cursor = None

        while True:
            response = await self.get_simcards(cursor=cursor)
            _LOGGER.debug(
                "get_all_simcards response keys: %s",
                list(response.keys()) if isinstance(response, dict) else type(response)
            )

            # Handle different response formats
            if isinstance(response, list):
                # Response is directly a list
                simcards.extend(response)
                break
            elif isinstance(response, dict):
                # Response is wrapped in an object - try various keys
                data = (
                    response.get("data")
                    or response.get("simcards")
                    or response.get("items")
                    or response.get("results")
                    or []
                )
                if isinstance(data, list):
                    simcards.extend(data)
                elif isinstance(data, dict):
                    # Single item response
                    simcards.append(data)

                # Check for pagination
                has_more = response.get("has_more", False) or response.get("hasMore", False)
                if not has_more:
                    break

                cursor = (
                    response.get("cursor")
                    or response.get("next_cursor")
                    or response.get("nextCursor")
                )
                if not cursor:
                    break
            else:
                _LOGGER.warning("Unexpected response type: %s", type(response))
                break

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)

        _LOGGER.debug("Total SIM cards fetched: %d", len(simcards))
        return simcards

    async def get_simcard(self, iccid: str) -> dict[str, Any]:
        """Get the full details of a specific SIM card by ICCID.

        The details response includes ``connection``, ``location``,
        ``session_status`` and ``throttle`` which are not present in the
        ``/simcards`` list response.
        """
        return await self._request("GET", f"{API_ENDPOINT_SIMCARDS}/{iccid}")

    async def set_simcard_state(self, iccid: str, state: str) -> dict[str, Any]:
        """Set a SIM card state via POST /simcards/{iccid}/state.

        ``state`` must be one of ``enabled`` or ``disabled``.
        """
        return await self._request(
            "POST",
            f"{API_ENDPOINT_SIMCARDS}/{iccid}/state",
            json_data={"state": state},
        )

    async def activate_simcard(self, iccid: str) -> dict[str, Any]:
        """Activate (enable) a SIM card."""
        return await self.set_simcard_state(iccid, "enabled")

    async def deactivate_simcard(self, iccid: str) -> dict[str, Any]:
        """Deactivate (disable) a SIM card."""
        return await self.set_simcard_state(iccid, "disabled")

    async def reset_simcard(self, iccid: str) -> dict[str, Any]:
        """Reset a SIM card connection (cancel the current data session)."""
        return await self._request(
            "POST",
            f"{API_ENDPOINT_SIMCARDS}/{iccid}/reset",
        )

    async def set_autodisable(
        self, iccid: str, autodisable: str | None
    ) -> dict[str, Any]:
        """Set or clear the auto-disable date for a SIM card.

        ``autodisable`` is an ISO date (``YYYY-MM-DD``) in the future, or
        ``None`` to disable the feature.
        """
        return await self._request(
            "POST",
            f"{API_ENDPOINT_SIMCARDS}/{iccid}/autodisable",
            json_data={"autodisable": autodisable},
        )

    async def get_rateplan(self, iccid: str) -> dict[str, Any]:
        """Get the rate plans assigned to a SIM card."""
        return await self._request(
            "GET",
            f"{API_ENDPOINT_SIMCARDS}/{iccid}/rateplan",
        )

    async def set_rateplan(self, iccid: str, plan_id: str) -> dict[str, Any]:
        """Assign a rate plan to a SIM card."""
        return await self._request(
            "POST",
            f"{API_ENDPOINT_SIMCARDS}/{iccid}/rateplan",
            json_data={"plan_id": plan_id},
        )

    async def get_cdrs(
        self,
        iccid: str,
        month: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Get call detail records (CDRs) for a SIM card."""
        params: dict[str, Any] = {"limit": limit}
        if month:
            params["month"] = month
        if cursor:
            params["cursor"] = cursor
        return await self._request(
            "GET",
            f"{API_ENDPOINT_SIMCARDS}/{iccid}/cdrs",
            params=params,
        )

    async def get_location_updates(
        self,
        iccid: str,
        month: str | None = None,
        day: str | None = None,
        country: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Get location updates (network attach history) for a SIM card."""
        params: dict[str, Any] = {"limit": limit}
        if month:
            params["month"] = month
        if day:
            params["day"] = day
        if country:
            params["country"] = country
        if cursor:
            params["cursor"] = cursor
        return await self._request(
            "GET",
            f"{API_ENDPOINT_SIMCARDS}/{iccid}/location-updates",
            params=params,
        )

    async def get_usage(
        self,
        cursor: str | None = None,
        limit: int = 100,
        month: str | None = None,
    ) -> dict[str, Any]:
        """Get usage data for SIM cards.

        ``month`` (``YYYY-MM``) filters by month; defaults to the current month.
        """
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if month:
            params["month"] = month
        return await self._request("GET", API_ENDPOINT_USAGE, params=params)

    async def get_all_usage(self) -> list[dict[str, Any]]:
        """Get all usage data with pagination."""
        usage_data = []
        cursor = None

        while True:
            response = await self.get_usage(cursor=cursor)
            # The v2 usage endpoint returns records under "simcards".
            data = (
                response.get("simcards")
                or response.get("data")
                or []
            )
            usage_data.extend(data)

            if not response.get("has_more", False):
                break

            cursor = response.get("cursor")
            if not cursor:
                break

            await asyncio.sleep(0.1)

        return usage_data

    async def send_sms(self, iccid: str, message: str) -> dict[str, Any]:
        """Send SMS to a SIM card."""
        return await self._request(
            "POST",
            f"{API_ENDPOINT_SIMCARDS}/{iccid}/sms",
            json_data={"message": message},
        )

    async def get_sms(
        self,
        iccid: str,
        limit: int = 50,
        direction: str | None = None,
        day: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get SMS messages for a SIM card.

        ``direction`` filters by ``mt`` (received) or ``mo`` (sent);
        ``day`` (``YYYY-MM-DD``) filters by day.
        """
        params: dict[str, Any] = {"limit": limit}
        if direction:
            params["direction"] = direction
        if day:
            params["day"] = day
        try:
            response = await self._request(
                "GET",
                f"{API_ENDPOINT_SIMCARDS}/{iccid}/sms",
                params=params,
            )
            # Handle different response formats
            if isinstance(response, list):
                return response
            elif isinstance(response, dict):
                return (
                    response.get("data")
                    or response.get("messages")
                    or response.get("sms")
                    or response.get("items")
                    or []
                )
            return []
        except SimbaseApiError as err:
            _LOGGER.debug("Could not fetch SMS for %s: %s", iccid, err)
            return []

    async def update_simcard(
        self,
        iccid: str,
        name: Any = UNSET,
        tags: Any = UNSET,
        imei_lock: Any = UNSET,
        throttling_policy: Any = UNSET,
        usage_limits_auto_enable: Any = UNSET,
        usage_limits_data_threshold: Any = UNSET,
        usage_limits_sms_threshold: Any = UNSET,
    ) -> dict[str, Any]:
        """Update SIM card details via PATCH /simcards/{iccid}.

        Any argument left as ``UNSET`` is omitted from the request; passing an
        explicit ``None`` sends ``null`` to clear a nullable field.
        """
        candidates = {
            "name": name,
            "tags": tags,
            "imei_lock": imei_lock,
            "throttling_policy": throttling_policy,
            "usage_limits_auto_enable": usage_limits_auto_enable,
            "usage_limits_data_threshold": usage_limits_data_threshold,
            "usage_limits_sms_threshold": usage_limits_sms_threshold,
        }
        data = {key: value for key, value in candidates.items() if value is not UNSET}
        return await self._request(
            "PATCH",
            f"{API_ENDPOINT_SIMCARDS}/{iccid}",
            json_data=data,
        )

    async def set_imei_lock(self, iccid: str, enabled: bool) -> dict[str, Any]:
        """Turn theft protection (IMEI lock) on or off for a SIM.

        The API models ``imei_lock`` as the string enum ``"on"`` / ``"off"``.
        """
        return await self.update_simcard(
            iccid, imei_lock="on" if enabled else "off"
        )

    async def set_usage_limits(
        self,
        iccid: str,
        auto_enable: Any = UNSET,
        data_threshold: Any = UNSET,
        sms_threshold: Any = UNSET,
    ) -> dict[str, Any]:
        """Set or clear usage limits for a SIM.

        Pass ``None`` for ``data_threshold``/``sms_threshold`` to clear the
        limit; omit an argument to leave it unchanged.
        """
        return await self.update_simcard(
            iccid,
            usage_limits_auto_enable=auto_enable,
            usage_limits_data_threshold=data_threshold,
            usage_limits_sms_threshold=sms_threshold,
        )

    async def get_balance(self) -> dict[str, Any]:
        """Get account balance (GET /account/balance)."""
        try:
            return await self._request("GET", API_ENDPOINT_BALANCE)
        except SimbaseApiError:
            _LOGGER.debug("Balance endpoint not available")
            return {}

    async def get_account_plans(self) -> dict[str, Any]:
        """Get the rate plans available to the account (GET /account/plans)."""
        try:
            return await self._request("GET", API_ENDPOINT_PLANS)
        except SimbaseApiError:
            _LOGGER.debug("Account plans endpoint not available")
            return {}

    async def activate_all_simcards(self) -> list[dict[str, Any]]:
        """Activate all SIM cards."""
        results = []
        simcards = await self.get_all_simcards()
        for simcard in simcards:
            iccid = simcard.get("iccid")
            state = (simcard.get("state") or simcard.get("status") or "").lower()
            if iccid and state in ("disabled", "inactive"):
                try:
                    result = await self.activate_simcard(iccid)
                    results.append({"iccid": iccid, "success": True, "result": result})
                except SimbaseApiError as err:
                    results.append({"iccid": iccid, "success": False, "error": str(err)})
                await asyncio.sleep(0.1)  # Rate limit protection
        return results

    async def deactivate_all_simcards(self) -> list[dict[str, Any]]:
        """Deactivate all SIM cards."""
        results = []
        simcards = await self.get_all_simcards()
        for simcard in simcards:
            iccid = simcard.get("iccid")
            state = (simcard.get("state") or simcard.get("status") or "").lower()
            if iccid and state in ("enabled", "active"):
                try:
                    result = await self.deactivate_simcard(iccid)
                    results.append({"iccid": iccid, "success": True, "result": result})
                except SimbaseApiError as err:
                    results.append({"iccid": iccid, "success": False, "error": str(err)})
                await asyncio.sleep(0.1)  # Rate limit protection
        return results
