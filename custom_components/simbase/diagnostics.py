"""Diagnostics support for Simbase."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SimbaseDataUpdateCoordinator

TO_REDACT = {
    CONF_API_KEY,
    "iccid",
    "imei",
    "msisdn",
    "ip_address",
    "ip",
    "phone_number",
    "public_ip",
    "private_network_ip",
    "lat",
    "lon",
    "cell_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: SimbaseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator_data": async_redact_data(coordinator.data or {}, TO_REDACT),
        "simcard_count": len(coordinator.get_all_simcards()),
    }
