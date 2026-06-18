"""Device tracker platform for Simbase integration.

Reports the cell-based location (latitude/longitude) of each SIM card so it
appears on the Home Assistant map. Coordinates are approximate (derived from
the serving cell, not GPS) and may be unavailable when the network does not
return a position.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_ENABLE_DEVICE_TRACKER,
    DEFAULT_ENABLE_DEVICE_TRACKER,
)
from .coordinator import SimbaseDataUpdateCoordinator
from .entity import SimbaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Simbase device trackers based on a config entry."""
    if not entry.options.get(
        CONF_ENABLE_DEVICE_TRACKER, DEFAULT_ENABLE_DEVICE_TRACKER
    ):
        return

    coordinator: SimbaseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    async_add_entities(
        SimbaseDeviceTracker(coordinator, iccid)
        for iccid in coordinator.get_all_simcards()
    )


class SimbaseDeviceTracker(SimbaseEntity, TrackerEntity):
    """Cell-based location tracker for a SIM card."""

    # Use the device (SIM) name as the entity name, as is conventional for
    # the primary tracker entity of a device.
    _attr_name = None
    _attr_icon = "mdi:map-marker-radius"

    def __init__(
        self, coordinator: SimbaseDataUpdateCoordinator, iccid: str
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator, iccid)
        self._attr_unique_id = f"{iccid}_tracker"

    def _location(self) -> dict[str, Any]:
        """Return the SIM's location object."""
        location = self._get_sim_data().get("location")
        return location if isinstance(location, dict) else {}

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the location."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the SIM, if known."""
        return self._location().get("lat")

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the SIM, if known."""
        return self._location().get("lon")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional location context."""
        location = self._location()
        return {
            "iccid": self._iccid,
            "carrier": location.get("carrier"),
            "country": location.get("country"),
            "cell_id": location.get("cell_id"),
            "lac": location.get("lac"),
            "radio": location.get("radio"),
            "last_update": location.get("last_update"),
        }
