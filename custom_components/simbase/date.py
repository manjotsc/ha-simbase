"""Date platform for Simbase integration (auto-disable date)."""
from __future__ import annotations

import logging
from datetime import date

from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SimbaseApiError
from .const import (
    DOMAIN,
    CONF_ENABLE_PLAN_CONTROLS,
    DEFAULT_ENABLE_PLAN_CONTROLS,
)
from .coordinator import SimbaseDataUpdateCoordinator
from .entity import SimbaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Simbase date entities based on a config entry."""
    if not entry.options.get(CONF_ENABLE_PLAN_CONTROLS, DEFAULT_ENABLE_PLAN_CONTROLS):
        return

    coordinator: SimbaseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    async_add_entities(
        SimbaseAutodisableDate(coordinator, iccid)
        for iccid in coordinator.get_all_simcards()
    )


class SimbaseAutodisableDate(SimbaseEntity, DateEntity):
    """Date on which the SIM card is automatically disabled."""

    _attr_translation_key = "autodisable"
    _attr_icon = "mdi:calendar-remove"

    def __init__(
        self, coordinator: SimbaseDataUpdateCoordinator, iccid: str
    ) -> None:
        """Initialize the auto-disable date entity."""
        super().__init__(coordinator, iccid)
        self._attr_unique_id = f"{iccid}_autodisable"

    @property
    def native_value(self) -> date | None:
        """Return the configured auto-disable date, if any."""
        value = self._get_sim_data().get("autodisable")
        if not value:
            return None
        try:
            # The API returns an ISO date such as "2025-12-31"; tolerate a
            # trailing time component if present.
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            _LOGGER.debug("Unparseable autodisable value for %s: %s", self._iccid, value)
            return None

    async def async_set_value(self, value: date) -> None:
        """Schedule the auto-disable date.

        Use the ``simbase.set_autodisable`` service to clear it.
        """
        try:
            await self.coordinator.async_set_autodisable(
                self._iccid, value.isoformat()
            )
        except SimbaseApiError as err:
            _LOGGER.error(
                "Failed to set auto-disable date for %s: %s", self._iccid, err
            )
            raise
