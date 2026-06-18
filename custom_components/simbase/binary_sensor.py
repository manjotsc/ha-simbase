"""Binary sensor platform for Simbase integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_ENABLE_BINARY_SENSORS, DEFAULT_BINARY_SENSORS
from .coordinator import SimbaseDataUpdateCoordinator
from .entity import SimbaseEntity


@dataclass(frozen=True, kw_only=True)
class SimbaseBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Simbase binary sensor entity."""

    is_on_fn: Callable[[dict[str, Any]], bool | None]
    attr_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _is_sim_online(data: dict[str, Any]) -> bool:
    """Check if SIM is online/enabled."""
    status = (data.get("status") or data.get("state") or "").lower()
    return status in ("active", "enabled", "online") or data.get("online") is True


def _is_throttled(data: dict[str, Any]) -> bool:
    """Check if the SIM card is currently throttled.

    The v2 details endpoint returns ``throttle`` as a string describing the
    active throttle policy, or null when not throttled.
    """
    return bool(data.get("throttle"))


BINARY_SENSOR_DESCRIPTIONS: tuple[SimbaseBinarySensorEntityDescription, ...] = (
    SimbaseBinarySensorEntityDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=_is_sim_online,
        attr_fn=lambda data: {
            "session_status": data.get("session_status"),
        },
    ),
    SimbaseBinarySensorEntityDescription(
        key="throttled",
        translation_key="throttled",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_is_throttled,
        attr_fn=lambda data: {
            "throttle": data.get("throttle"),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Simbase binary sensors based on a config entry."""
    coordinator: SimbaseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    # Get enabled binary sensors from options
    enabled_binary_sensors = entry.options.get(
        CONF_ENABLE_BINARY_SENSORS, DEFAULT_BINARY_SENSORS
    )

    entities: list[SimbaseBinarySensor] = []

    for iccid in coordinator.get_all_simcards():
        for description in BINARY_SENSOR_DESCRIPTIONS:
            # Only add binary sensor if it's enabled in options
            if description.key in enabled_binary_sensors:
                entities.append(SimbaseBinarySensor(coordinator, iccid, description))

    async_add_entities(entities)


class SimbaseBinarySensor(SimbaseEntity, BinarySensorEntity):
    """Representation of a Simbase binary sensor."""

    entity_description: SimbaseBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SimbaseDataUpdateCoordinator,
        iccid: str,
        description: SimbaseBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, iccid)
        self.entity_description = description
        self._attr_unique_id = f"{iccid}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        sim_data = self._get_sim_data()
        return self.entity_description.is_on_fn(sim_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes."""
        if self.entity_description.attr_fn is None:
            return {"iccid": self._iccid}
        sim_data = self._get_sim_data()
        attrs = self.entity_description.attr_fn(sim_data)
        attrs["iccid"] = self._iccid
        return attrs
