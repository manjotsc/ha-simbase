"""Number platform for Simbase integration (usage limits)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SimbaseApiError
from .const import (
    DOMAIN,
    BYTES_PER_MB,
    CONF_ENABLE_USAGE_LIMITS,
    DEFAULT_ENABLE_USAGE_LIMITS,
)
from .coordinator import SimbaseDataUpdateCoordinator
from .entity import SimbaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Simbase number entities based on a config entry."""
    if not entry.options.get(CONF_ENABLE_USAGE_LIMITS, DEFAULT_ENABLE_USAGE_LIMITS):
        return

    coordinator: SimbaseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities: list[NumberEntity] = []
    for iccid in coordinator.get_all_simcards():
        entities.append(SimbaseDataLimitNumber(coordinator, iccid))
        entities.append(SimbaseSmsLimitNumber(coordinator, iccid))

    async_add_entities(entities)


class SimbaseDataLimitNumber(SimbaseEntity, NumberEntity):
    """Data usage limit (usage_limits_data_threshold), expressed in MB."""

    _attr_translation_key = "data_limit"
    _attr_device_class = NumberDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES
    _attr_native_min_value = 10  # API minimum is 10,000,000 bytes (10 MB)
    _attr_native_max_value = 1000000  # 1 TB expressed in MB
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:database-arrow-up"

    def __init__(
        self, coordinator: SimbaseDataUpdateCoordinator, iccid: str
    ) -> None:
        """Initialize the data limit number."""
        super().__init__(coordinator, iccid)
        self._attr_unique_id = f"{iccid}_data_limit"

    @property
    def native_value(self) -> float | None:
        """Return the current data threshold in MB."""
        threshold = self._get_sim_data().get("usage_limits_data_threshold")
        if threshold is None:
            return None
        return round(threshold / BYTES_PER_MB, 2)

    async def async_set_native_value(self, value: float) -> None:
        """Set the data threshold (converted from MB to bytes)."""
        try:
            await self.coordinator.async_set_usage_limits(
                self._iccid, data_threshold=int(value * BYTES_PER_MB)
            )
        except SimbaseApiError as err:
            _LOGGER.error("Failed to set data limit for %s: %s", self._iccid, err)
            raise


class SimbaseSmsLimitNumber(SimbaseEntity, NumberEntity):
    """SMS usage limit (usage_limits_sms_threshold), in messages."""

    _attr_translation_key = "sms_limit"
    _attr_native_unit_of_measurement = "messages"
    _attr_native_min_value = 1  # API minimum is 1 SMS
    _attr_native_max_value = 100000
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:message-alert"

    def __init__(
        self, coordinator: SimbaseDataUpdateCoordinator, iccid: str
    ) -> None:
        """Initialize the SMS limit number."""
        super().__init__(coordinator, iccid)
        self._attr_unique_id = f"{iccid}_sms_limit"

    @property
    def native_value(self) -> float | None:
        """Return the current SMS threshold."""
        threshold = self._get_sim_data().get("usage_limits_sms_threshold")
        if threshold is None:
            return None
        return float(threshold)

    async def async_set_native_value(self, value: float) -> None:
        """Set the SMS threshold."""
        try:
            await self.coordinator.async_set_usage_limits(
                self._iccid, sms_threshold=int(value)
            )
        except SimbaseApiError as err:
            _LOGGER.error("Failed to set SMS limit for %s: %s", self._iccid, err)
            raise
