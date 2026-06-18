"""Button platform for Simbase integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SimbaseApiError
from .const import (
    DOMAIN,
    CONF_ENABLE_RESET_BUTTON,
    DEFAULT_ENABLE_RESET_BUTTON,
)
from .coordinator import SimbaseDataUpdateCoordinator
from .entity import SimbaseAccountEntity, SimbaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SimbaseButtonEntityDescription(ButtonEntityDescription):
    """Describes Simbase button entity."""

    press_action: str


BUTTON_DESCRIPTIONS: tuple[SimbaseButtonEntityDescription, ...] = (
    SimbaseButtonEntityDescription(
        key="activate_all_sims",
        translation_key="activate_all_sims",
        icon="mdi:sim",
        press_action="activate_all",
    ),
    SimbaseButtonEntityDescription(
        key="deactivate_all_sims",
        translation_key="deactivate_all_sims",
        icon="mdi:sim-off",
        press_action="deactivate_all",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Simbase buttons based on a config entry."""
    coordinator: SimbaseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities: list[ButtonEntity] = []

    for description in BUTTON_DESCRIPTIONS:
        entities.append(SimbaseAccountButton(coordinator, entry.entry_id, description))

    # Per-SIM reset connection button
    if entry.options.get(CONF_ENABLE_RESET_BUTTON, DEFAULT_ENABLE_RESET_BUTTON):
        for iccid in coordinator.get_all_simcards():
            entities.append(SimbaseResetConnectionButton(coordinator, iccid))

    async_add_entities(entities)


class SimbaseAccountButton(SimbaseAccountEntity, ButtonEntity):
    """Representation of a Simbase account button."""

    entity_description: SimbaseButtonEntityDescription

    def __init__(
        self,
        coordinator: SimbaseDataUpdateCoordinator,
        entry_id: str,
        description: SimbaseButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"account_{entry_id}_{description.key}"

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.entity_description.press_action == "activate_all":
            _LOGGER.info("Activating all SIM cards")
            results = await self.coordinator.async_activate_all_simcards()
            _LOGGER.debug("Activate all results: %s", results)
        elif self.entity_description.press_action == "deactivate_all":
            _LOGGER.info("Deactivating all SIM cards")
            results = await self.coordinator.async_deactivate_all_simcards()
            _LOGGER.debug("Deactivate all results: %s", results)


class SimbaseResetConnectionButton(SimbaseEntity, ButtonEntity):
    """Button to reset a SIM card's connection (cancel the data session)."""

    _attr_translation_key = "reset_connection"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_icon = "mdi:restart"

    def __init__(
        self,
        coordinator: SimbaseDataUpdateCoordinator,
        iccid: str,
    ) -> None:
        """Initialize the reset connection button."""
        super().__init__(coordinator, iccid)
        self._attr_unique_id = f"{iccid}_reset_connection"

    async def async_press(self) -> None:
        """Reset the SIM card connection."""
        try:
            await self.coordinator.async_reset_connection(self._iccid)
        except SimbaseApiError as err:
            _LOGGER.error("Failed to reset connection for %s: %s", self._iccid, err)
            raise
