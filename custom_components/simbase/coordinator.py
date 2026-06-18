"""Data coordinator for Simbase integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SimbaseApiClient, SimbaseApiError
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, UNSET

_LOGGER = logging.getLogger(__name__)


class SimbaseDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Simbase data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: SimbaseApiClient,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api_client = api_client
        self._simcards: dict[str, dict[str, Any]] = {}
        self._usage: dict[str, dict[str, Any]] = {}
        self._balance: dict[str, Any] = {}
        self._plans: list[dict[str, Any]] = []

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            # Fetch all SIM cards
            _LOGGER.debug("Fetching SIM cards from Simbase API")
            simcards = await self.api_client.get_all_simcards()
            _LOGGER.debug("Received %d SIM cards", len(simcards))

            # Build simcards dict - handle different response formats
            self._simcards = {}
            for sim in simcards:
                # Try different possible ICCID field names
                iccid = sim.get("iccid") or sim.get("ICCID") or sim.get("id")
                if iccid:
                    self._simcards[iccid] = sim
                    _LOGGER.debug("Added SIM with ICCID: %s, data: %s", iccid, sim)
                else:
                    _LOGGER.warning("SIM card without ICCID found: %s", sim)

            _LOGGER.info("Found %d SIM cards in Simbase account", len(self._simcards))

            # Fetch usage data
            try:
                usage_data = await self.api_client.get_all_usage()
                self._usage = {}
                for u in usage_data:
                    iccid = u.get("iccid") or u.get("ICCID") or u.get("id")
                    if iccid:
                        self._usage[iccid] = u
            except SimbaseApiError as err:
                _LOGGER.warning("Failed to fetch usage data: %s", err)
                # Continue with simcard data even if usage fails

            # Merge usage data into simcards
            for iccid, sim in self._simcards.items():
                if iccid in self._usage:
                    sim["usage"] = self._usage[iccid]

            # Fetch per-SIM details to enrich with connection / location /
            # session status / throttle, which the /simcards list omits.
            for iccid, sim in self._simcards.items():
                try:
                    details = await self.api_client.get_simcard(iccid)
                except SimbaseApiError as err:
                    _LOGGER.debug("Failed to fetch details for %s: %s", iccid, err)
                    continue
                if not isinstance(details, dict):
                    continue
                # Merge detail-only fields into the SIM record.
                for key in (
                    "connection",
                    "location",
                    "session_status",
                    "throttle",
                ):
                    if key in details:
                        sim[key] = details[key]
                # Derive the network operator from the live connection.
                connection = details.get("connection") or {}
                if isinstance(connection, dict):
                    if connection.get("carrier"):
                        sim["network_operator"] = connection["carrier"]
                    if connection.get("mcc"):
                        sim["mcc"] = connection["mcc"]
                    if connection.get("mnc"):
                        sim["mnc"] = connection["mnc"]
                await asyncio.sleep(0.1)  # Rate limit protection

            # Fetch balance data
            try:
                self._balance = await self.api_client.get_balance()
                _LOGGER.debug("Balance data: %s", self._balance)
            except SimbaseApiError as err:
                _LOGGER.debug("Failed to fetch balance data: %s", err)
                self._balance = {}

            # Fetch available rate plans (for the rate plan select entity)
            try:
                plans_response = await self.api_client.get_account_plans()
                plans = plans_response.get("plans") if isinstance(plans_response, dict) else None
                self._plans = plans if isinstance(plans, list) else []
            except SimbaseApiError as err:
                _LOGGER.debug("Failed to fetch account plans: %s", err)

            # Calculate totals from SIM data
            total_data_usage = 0
            total_cost = 0.0
            active_sims = 0
            inactive_sims = 0
            total_sms_sent = 0
            total_sms_received = 0
            for sim in self._simcards.values():
                # Data usage
                current_month = sim.get("current_month_usage", {})
                if isinstance(current_month, dict):
                    data_bytes = current_month.get("data", 0) or 0
                    total_data_usage += data_bytes
                    # SMS counts
                    sms_mo = current_month.get("sms_mo", 0) or 0
                    sms_mt = current_month.get("sms_mt", 0) or 0
                    total_sms_sent += sms_mo
                    total_sms_received += sms_mt
                # Cost
                current_costs = sim.get("current_month_costs", {})
                if isinstance(current_costs, dict):
                    cost = current_costs.get("total")
                    if cost:
                        try:
                            total_cost += float(cost)
                        except (ValueError, TypeError):
                            pass
                # Status
                state = (sim.get("state") or sim.get("status") or "").lower()
                if state in ("enabled", "active"):
                    active_sims += 1
                else:
                    inactive_sims += 1

            return {
                "simcards": self._simcards,
                "usage": self._usage,
                "count": len(self._simcards),
                "balance": self._balance,
                "totals": {
                    "data_usage_bytes": total_data_usage,
                    "data_usage_mb": round(total_data_usage / (1024 * 1024), 2) if total_data_usage else 0,
                    "total_cost": round(total_cost, 2),
                    "active_sims": active_sims,
                    "inactive_sims": inactive_sims,
                    "sms_sent": total_sms_sent,
                    "sms_received": total_sms_received,
                    "sms_total": total_sms_sent + total_sms_received,
                },
            }

        except SimbaseApiError as err:
            _LOGGER.error("Error communicating with Simbase API: %s", err)
            raise UpdateFailed(f"Error communicating with Simbase API: {err}") from err

    def get_simcard(self, iccid: str) -> dict[str, Any] | None:
        """Get a specific SIM card by ICCID."""
        return self._simcards.get(iccid)

    def get_all_simcards(self) -> dict[str, dict[str, Any]]:
        """Get all SIM cards."""
        return self._simcards

    async def async_activate_simcard(self, iccid: str) -> None:
        """Activate a SIM card."""
        await self.api_client.activate_simcard(iccid)
        await self.async_request_refresh()

    async def async_deactivate_simcard(self, iccid: str) -> None:
        """Deactivate a SIM card."""
        await self.api_client.deactivate_simcard(iccid)
        await self.async_request_refresh()

    async def async_send_sms(self, iccid: str, message: str) -> None:
        """Send SMS to a SIM card."""
        await self.api_client.send_sms(iccid, message)

    async def async_reset_connection(self, iccid: str) -> None:
        """Reset a SIM card connection (cancel the current data session)."""
        await self.api_client.reset_simcard(iccid)
        await self.async_request_refresh()

    async def async_set_autodisable(
        self, iccid: str, autodisable: str | None
    ) -> None:
        """Set or clear the auto-disable date for a SIM card."""
        await self.api_client.set_autodisable(iccid, autodisable)
        await self.async_request_refresh()

    async def async_set_usage_limits(
        self,
        iccid: str,
        auto_enable: Any = UNSET,
        data_threshold: Any = UNSET,
        sms_threshold: Any = UNSET,
    ) -> None:
        """Set or clear usage limits for a SIM card.

        Pass ``None`` for a threshold to clear it; omit to leave unchanged.
        """
        await self.api_client.set_usage_limits(
            iccid,
            auto_enable=auto_enable,
            data_threshold=data_threshold,
            sms_threshold=sms_threshold,
        )
        # Await an immediate refresh so entities read the confirmed value
        # rather than the pre-write (debounced) data.
        await self.async_refresh()

    async def async_set_rateplan(self, iccid: str, plan_id: str) -> None:
        """Assign a rate plan to a SIM card."""
        await self.api_client.set_rateplan(iccid, plan_id)
        await self.async_request_refresh()

    def get_account_data(self) -> dict[str, Any]:
        """Get account data (no longer provided by the v2 API)."""
        return {}

    def get_rate_plans(self) -> list[dict[str, Any]]:
        """Return the rate plans available to the account."""
        return self._plans

    def get_balance(self) -> dict[str, Any]:
        """Get balance data."""
        return self._balance

    def get_totals(self) -> dict[str, Any]:
        """Get calculated totals."""
        if self.data:
            return self.data.get("totals", {})
        return {}

    async def async_activate_all_simcards(self) -> list[dict[str, Any]]:
        """Activate all SIM cards."""
        results = await self.api_client.activate_all_simcards()
        await self.async_request_refresh()
        return results

    async def async_deactivate_all_simcards(self) -> list[dict[str, Any]]:
        """Deactivate all SIM cards."""
        results = await self.api_client.deactivate_all_simcards()
        await self.async_request_refresh()
        return results
