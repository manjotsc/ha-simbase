"""Switch platform for Simbase integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SimbaseApiError
from .const import (
    DOMAIN,
    BYTES_PER_MB,
    CONF_ENABLE_SWITCH,
    CONF_ENABLE_USAGE_LIMITS,
    CONF_ENABLE_THEFT_PROTECTION,
    DEFAULT_ENABLE_SWITCH,
    DEFAULT_ENABLE_USAGE_LIMITS,
    DEFAULT_ENABLE_THEFT_PROTECTION,
    DEFAULT_DATA_LIMIT_MB,
    DEFAULT_SMS_LIMIT,
)
from .coordinator import SimbaseDataUpdateCoordinator
from .entity import SimbaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Simbase switches based on a config entry."""
    coordinator: SimbaseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    activation_enabled = entry.options.get(CONF_ENABLE_SWITCH, DEFAULT_ENABLE_SWITCH)
    usage_limits_enabled = entry.options.get(
        CONF_ENABLE_USAGE_LIMITS, DEFAULT_ENABLE_USAGE_LIMITS
    )
    theft_protection_enabled = entry.options.get(
        CONF_ENABLE_THEFT_PROTECTION, DEFAULT_ENABLE_THEFT_PROTECTION
    )

    entities: list[SwitchEntity] = []
    for iccid in coordinator.get_all_simcards():
        if activation_enabled:
            entities.append(SimbaseActivationSwitch(coordinator, iccid))
        if theft_protection_enabled:
            entities.append(SimbaseTheftProtectionSwitch(coordinator, iccid))
        if usage_limits_enabled:
            entities.append(SimbaseAutoEnableSwitch(coordinator, iccid))
            entities.append(SimbaseDataLimitSwitch(coordinator, iccid))
            entities.append(SimbaseSmsLimitSwitch(coordinator, iccid))

    async_add_entities(entities)


class SimbaseActivationSwitch(SimbaseEntity, SwitchEntity):
    """Switch to activate/deactivate a SIM card."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_translation_key = "activation"

    def __init__(
        self,
        coordinator: SimbaseDataUpdateCoordinator,
        iccid: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, iccid)
        self._attr_unique_id = f"{iccid}_activation"

    @property
    def is_on(self) -> bool | None:
        """Return true if the SIM is active/enabled."""
        sim_data = self._get_sim_data()
        status = sim_data.get("status") or sim_data.get("state")
        if status is None:
            return None
        return status.lower() in ("active", "enabled")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        sim_data = self._get_sim_data()
        return {
            "iccid": self._iccid,
            "status": sim_data.get("status") or sim_data.get("state"),
            "activated_at": sim_data.get("activated_at"),
            "suspended_at": sim_data.get("suspended_at"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate the SIM card."""
        try:
            await self.coordinator.async_activate_simcard(self._iccid)
        except SimbaseApiError as err:
            _LOGGER.error("Failed to activate SIM %s: %s", self._iccid, err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deactivate the SIM card."""
        try:
            await self.coordinator.async_deactivate_simcard(self._iccid)
        except SimbaseApiError as err:
            _LOGGER.error("Failed to deactivate SIM %s: %s", self._iccid, err)
            raise


class SimbaseTheftProtectionSwitch(SimbaseEntity, SwitchEntity):
    """Theft protection / IMEI lock, locking the SIM to its current device.

    The API models ``imei_lock`` as the string enum ``"on"`` / ``"off"``.
    """

    _attr_translation_key = "theft_protection"
    _attr_icon = "mdi:shield-lock"

    def __init__(
        self,
        coordinator: SimbaseDataUpdateCoordinator,
        iccid: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, iccid)
        self._attr_unique_id = f"{iccid}_theft_protection"

    @property
    def is_on(self) -> bool | None:
        """Return whether the SIM is locked to its device's IMEI."""
        value = self._get_sim_data().get("imei_lock")
        if value is None:
            return None
        return str(value).lower() == "on"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the IMEI the SIM is locked to."""
        return {"imei": self._get_sim_data().get("imei")}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Lock the SIM to its current device."""
        try:
            await self.coordinator.async_set_imei_lock(self._iccid, True)
        except SimbaseApiError as err:
            _LOGGER.error(
                "Failed to enable theft protection for %s: %s", self._iccid, err
            )
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Allow the SIM to be used in any device."""
        try:
            await self.coordinator.async_set_imei_lock(self._iccid, False)
        except SimbaseApiError as err:
            _LOGGER.error(
                "Failed to disable theft protection for %s: %s", self._iccid, err
            )
            raise


class SimbaseAutoEnableSwitch(SimbaseEntity, SwitchEntity):
    """Switch for the monthly usage-limit auto re-enable behaviour."""

    _attr_translation_key = "usage_limits_auto_enable"
    _attr_icon = "mdi:calendar-refresh"

    def __init__(
        self,
        coordinator: SimbaseDataUpdateCoordinator,
        iccid: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, iccid)
        self._attr_unique_id = f"{iccid}_usage_limits_auto_enable"

    @property
    def is_on(self) -> bool | None:
        """Return whether the SIM auto re-enables each month."""
        value = self._get_sim_data().get("usage_limits_auto_enable")
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable monthly auto re-enable."""
        try:
            await self.coordinator.async_set_usage_limits(self._iccid, auto_enable=True)
        except SimbaseApiError as err:
            _LOGGER.error("Failed to set auto re-enable for %s: %s", self._iccid, err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable monthly auto re-enable."""
        try:
            await self.coordinator.async_set_usage_limits(self._iccid, auto_enable=False)
        except SimbaseApiError as err:
            _LOGGER.error("Failed to set auto re-enable for %s: %s", self._iccid, err)
            raise


class _UsageLimitSwitch(SimbaseEntity, SwitchEntity):
    """Base class for the data/SMS usage-limit enable switches.

    The switch reflects whether a threshold is set. Turning it off clears the
    threshold; turning it on restores the last known value (or a default).

    State is optimistic: the user's intent is shown immediately and held until
    the coordinator confirms the API reflects it, so the toggle does not bounce
    back on while a write is still propagating.
    """

    # Overridden by subclasses.
    _threshold_field: str

    def __init__(
        self,
        coordinator: SimbaseDataUpdateCoordinator,
        iccid: str,
        last_threshold: int,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, iccid)
        self._last_threshold = last_threshold
        self._optimistic: bool | None = None

    def _current_threshold(self) -> int | None:
        """Return the threshold currently reported by the API."""
        return self._get_sim_data().get(self._threshold_field)

    @property
    def is_on(self) -> bool:
        """Return whether the limit is enabled (optimistic-aware)."""
        if self._optimistic is not None:
            return self._optimistic
        threshold = self._current_threshold()
        if threshold is not None:
            self._last_threshold = threshold
            return True
        return False

    def _handle_coordinator_update(self) -> None:
        """Clear the optimistic state once the API confirms the intent."""
        if self._optimistic is not None:
            if (self._current_threshold() is not None) == self._optimistic:
                self._optimistic = None
        super()._handle_coordinator_update()

    async def _apply(self, threshold: int | None) -> None:
        """Send the new threshold, reflecting intent optimistically."""
        self._optimistic = threshold is not None
        self.async_write_ha_state()
        try:
            await self.coordinator.async_set_usage_limits(
                self._iccid, **{self._coordinator_kwarg: threshold}
            )
        except SimbaseApiError as err:
            self._optimistic = None
            self.async_write_ha_state()
            _LOGGER.error(
                "Failed to update %s for %s: %s",
                self._threshold_field,
                self._iccid,
                err,
            )
            raise

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the limit, restoring the last known threshold."""
        await self._apply(self._last_threshold)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable (clear) the limit."""
        await self._apply(None)


class SimbaseDataLimitSwitch(_UsageLimitSwitch):
    """Enable/disable the data usage limit (usage_limits_data_threshold)."""

    _attr_translation_key = "data_limit_enabled"
    _attr_icon = "mdi:database-alert"
    _threshold_field = "usage_limits_data_threshold"
    _coordinator_kwarg = "data_threshold"

    def __init__(
        self,
        coordinator: SimbaseDataUpdateCoordinator,
        iccid: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, iccid, DEFAULT_DATA_LIMIT_MB * BYTES_PER_MB)
        self._attr_unique_id = f"{iccid}_data_limit_enabled"


class SimbaseSmsLimitSwitch(_UsageLimitSwitch):
    """Enable/disable the SMS usage limit (usage_limits_sms_threshold)."""

    _attr_translation_key = "sms_limit_enabled"
    _attr_icon = "mdi:message-alert"
    _threshold_field = "usage_limits_sms_threshold"
    _coordinator_kwarg = "sms_threshold"

    def __init__(
        self,
        coordinator: SimbaseDataUpdateCoordinator,
        iccid: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, iccid, DEFAULT_SMS_LIMIT)
        self._attr_unique_id = f"{iccid}_sms_limit_enabled"
