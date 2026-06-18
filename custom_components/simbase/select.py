"""Select platform for Simbase integration (rate plan)."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
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
    """Set up Simbase select entities based on a config entry."""
    if not entry.options.get(CONF_ENABLE_PLAN_CONTROLS, DEFAULT_ENABLE_PLAN_CONTROLS):
        return

    coordinator: SimbaseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    async_add_entities(
        SimbaseRateplanSelect(coordinator, iccid)
        for iccid in coordinator.get_all_simcards()
    )


class SimbaseRateplanSelect(SimbaseEntity, SelectEntity):
    """Select entity to assign a rate plan to a SIM card."""

    _attr_translation_key = "rateplan"
    _attr_icon = "mdi:cash-multiple"

    def __init__(
        self, coordinator: SimbaseDataUpdateCoordinator, iccid: str
    ) -> None:
        """Initialize the rate plan select."""
        super().__init__(coordinator, iccid)
        self._attr_unique_id = f"{iccid}_rateplan"

    def _label_to_plan_id(self) -> dict[str, str]:
        """Build a mapping of option label -> plan_id.

        Labels are plan names, disambiguated with the plan_id when names
        collide. The SIM's current plan_id is always included so that
        ``current_option`` is a valid member of ``options``.
        """
        plans = self.coordinator.get_rate_plans()
        names = [p.get("name") for p in plans]
        mapping: dict[str, str] = {}
        for plan in plans:
            plan_id = plan.get("plan_id")
            if not plan_id:
                continue
            name = plan.get("name") or plan_id
            label = name if names.count(name) == 1 else f"{name} ({plan_id})"
            mapping[label] = plan_id

        current = self._get_sim_data().get("plan_id")
        if current and current not in mapping.values():
            mapping[current] = current
        return mapping

    @property
    def options(self) -> list[str]:
        """Return the selectable rate plan labels."""
        return sorted(self._label_to_plan_id())

    @property
    def current_option(self) -> str | None:
        """Return the currently assigned rate plan label."""
        current = self._get_sim_data().get("plan_id")
        if not current:
            return None
        for label, plan_id in self._label_to_plan_id().items():
            if plan_id == current:
                return label
        return None

    async def async_select_option(self, option: str) -> None:
        """Assign the chosen rate plan."""
        plan_id = self._label_to_plan_id().get(option, option)
        try:
            await self.coordinator.async_set_rateplan(self._iccid, plan_id)
        except SimbaseApiError as err:
            _LOGGER.error("Failed to set rate plan for %s: %s", self._iccid, err)
            raise
