"""The Simbase integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SimbaseApiClient
from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    SERVICE_ACTIVATE_SIM,
    SERVICE_DEACTIVATE_SIM,
    SERVICE_SEND_SMS,
    SERVICE_READ_SMS,
    SERVICE_RESET_CONNECTION,
    SERVICE_SET_AUTODISABLE,
    SERVICE_SET_USAGE_LIMITS,
    SERVICE_SET_RATEPLAN,
    UNSET,
)
from .coordinator import SimbaseDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.DATE,
    Platform.DEVICE_TRACKER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Simbase from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api_key = entry.data[CONF_API_KEY]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    session = async_get_clientsession(hass)
    api_client = SimbaseApiClient(api_key, session)

    coordinator = SimbaseDataUpdateCoordinator(
        hass,
        entry,
        api_client,
        scan_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await _async_setup_services(hass)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_iccid_from_device(hass: HomeAssistant, device_id: str) -> str | None:
    """Get ICCID from device ID."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device:
        for identifier in device.identifiers:
            if identifier[0] == DOMAIN:
                # The identifier is (DOMAIN, ICCID)
                return identifier[1]
    return None


async def _async_setup_services(hass: HomeAssistant) -> None:
    """Set up Simbase services."""

    async def async_activate_sim(call: ServiceCall) -> None:
        """Activate a SIM card."""
        device_id = call.data["device_id"]
        iccid = _get_iccid_from_device(hass, device_id)
        if not iccid:
            _LOGGER.error("Could not find ICCID for device %s", device_id)
            return
        for entry_data in hass.data[DOMAIN].values():
            coordinator: SimbaseDataUpdateCoordinator = entry_data["coordinator"]
            if coordinator.get_simcard(iccid):
                await coordinator.async_activate_simcard(iccid)
                return
        _LOGGER.error("SIM card with ICCID %s not found", iccid)

    async def async_deactivate_sim(call: ServiceCall) -> None:
        """Deactivate a SIM card."""
        device_id = call.data["device_id"]
        iccid = _get_iccid_from_device(hass, device_id)
        if not iccid:
            _LOGGER.error("Could not find ICCID for device %s", device_id)
            return
        for entry_data in hass.data[DOMAIN].values():
            coordinator: SimbaseDataUpdateCoordinator = entry_data["coordinator"]
            if coordinator.get_simcard(iccid):
                await coordinator.async_deactivate_simcard(iccid)
                return
        _LOGGER.error("SIM card with ICCID %s not found", iccid)

    async def async_send_sms(call: ServiceCall) -> None:
        """Send SMS to a SIM card."""
        device_id = call.data["device_id"]
        message = call.data["message"]
        iccid = _get_iccid_from_device(hass, device_id)
        if not iccid:
            _LOGGER.error("Could not find ICCID for device %s", device_id)
            return
        for entry_data in hass.data[DOMAIN].values():
            coordinator: SimbaseDataUpdateCoordinator = entry_data["coordinator"]
            if coordinator.get_simcard(iccid):
                await coordinator.async_send_sms(iccid, message)
                return
        _LOGGER.error("SIM card with ICCID %s not found", iccid)

    async def async_read_sms(call: ServiceCall) -> dict:
        """Read SMS messages from a SIM card."""
        device_id = call.data["device_id"]
        limit = call.data.get("limit", 50)
        iccid = _get_iccid_from_device(hass, device_id)
        if not iccid:
            _LOGGER.error("Could not find ICCID for device %s", device_id)
            return {"success": False, "error": "Device not found", "messages": []}
        for entry_data in hass.data[DOMAIN].values():
            api_client: SimbaseApiClient = entry_data["api_client"]
            coordinator: SimbaseDataUpdateCoordinator = entry_data["coordinator"]
            if coordinator.get_simcard(iccid):
                messages = await api_client.get_sms(iccid, limit=limit)
                return {"success": True, "iccid": iccid, "messages": messages, "count": len(messages)}
        _LOGGER.error("SIM card with ICCID %s not found", iccid)
        return {"success": False, "error": "SIM not found", "messages": []}

    def _resolve_coordinator(iccid: str) -> SimbaseDataUpdateCoordinator | None:
        """Return the coordinator that manages the given ICCID."""
        for entry_data in hass.data[DOMAIN].values():
            coordinator: SimbaseDataUpdateCoordinator = entry_data["coordinator"]
            if coordinator.get_simcard(iccid):
                return coordinator
        return None

    async def async_reset_connection(call: ServiceCall) -> None:
        """Reset a SIM card connection."""
        iccid = _get_iccid_from_device(hass, call.data["device_id"])
        if not iccid:
            _LOGGER.error("Could not find ICCID for device %s", call.data["device_id"])
            return
        coordinator = _resolve_coordinator(iccid)
        if coordinator is None:
            _LOGGER.error("SIM card with ICCID %s not found", iccid)
            return
        await coordinator.async_reset_connection(iccid)

    async def async_set_autodisable(call: ServiceCall) -> None:
        """Set or clear the auto-disable date for a SIM card."""
        iccid = _get_iccid_from_device(hass, call.data["device_id"])
        if not iccid:
            _LOGGER.error("Could not find ICCID for device %s", call.data["device_id"])
            return
        coordinator = _resolve_coordinator(iccid)
        if coordinator is None:
            _LOGGER.error("SIM card with ICCID %s not found", iccid)
            return
        # An empty/omitted date clears the auto-disable feature.
        date = call.data.get("date") or None
        await coordinator.async_set_autodisable(iccid, date)

    async def async_set_usage_limits(call: ServiceCall) -> None:
        """Set usage limits for a SIM card."""
        iccid = _get_iccid_from_device(hass, call.data["device_id"])
        if not iccid:
            _LOGGER.error("Could not find ICCID for device %s", call.data["device_id"])
            return
        coordinator = _resolve_coordinator(iccid)
        if coordinator is None:
            _LOGGER.error("SIM card with ICCID %s not found", iccid)
            return
        # Omitted fields stay UNSET (unchanged); only provided fields are sent.
        await coordinator.async_set_usage_limits(
            iccid,
            auto_enable=call.data.get("auto_enable", UNSET),
            data_threshold=call.data.get("data_threshold", UNSET),
            sms_threshold=call.data.get("sms_threshold", UNSET),
        )

    async def async_set_rateplan(call: ServiceCall) -> None:
        """Assign a rate plan to a SIM card."""
        iccid = _get_iccid_from_device(hass, call.data["device_id"])
        if not iccid:
            _LOGGER.error("Could not find ICCID for device %s", call.data["device_id"])
            return
        coordinator = _resolve_coordinator(iccid)
        if coordinator is None:
            _LOGGER.error("SIM card with ICCID %s not found", iccid)
            return
        await coordinator.async_set_rateplan(iccid, call.data["plan_id"])

    # Only register if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_ACTIVATE_SIM):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ACTIVATE_SIM,
            async_activate_sim,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_DEACTIVATE_SIM):
        hass.services.async_register(
            DOMAIN,
            SERVICE_DEACTIVATE_SIM,
            async_deactivate_sim,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_SMS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_SMS,
            async_send_sms,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_READ_SMS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_READ_SMS,
            async_read_sms,
            supports_response=SupportsResponse.OPTIONAL,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_RESET_CONNECTION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RESET_CONNECTION,
            async_reset_connection,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_AUTODISABLE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_AUTODISABLE,
            async_set_autodisable,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_USAGE_LIMITS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_USAGE_LIMITS,
            async_set_usage_limits,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_RATEPLAN):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_RATEPLAN,
            async_set_rateplan,
        )
