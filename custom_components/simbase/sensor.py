"""Sensor platform for Simbase integration."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_ENABLE_SENSORS, DEFAULT_SENSORS
from .coordinator import SimbaseDataUpdateCoordinator
from .entity import SimbaseEntity, SimbaseAccountEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SimbaseSensorEntityDescription(SensorEntityDescription):
    """Describes Simbase sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any]
    attr_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _bytes_to_mb(value: Any) -> float | None:
    """Convert bytes to megabytes."""
    if value is None:
        return None
    try:
        return round(float(value) / (1024 * 1024), 2)
    except (ValueError, TypeError):
        return None


def _to_float(value: Any) -> float | None:
    """Coerce an API value (often a decimal string) to a float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _get_data_usage(data: dict) -> float | None:
    """Get data usage in MB from Simbase API response."""
    # Simbase returns data in current_month_usage.data (bytes)
    current_month = data.get("current_month_usage", {})
    if isinstance(current_month, dict):
        data_bytes = current_month.get("data")
        if data_bytes is not None:
            return _bytes_to_mb(data_bytes)
    return None


def _get_data_cost(data: dict) -> float | None:
    """Get data cost from Simbase API response."""
    current_month = data.get("current_month_costs", {})
    if isinstance(current_month, dict):
        total = current_month.get("total")
        if total is not None:
            try:
                return float(total)
            except (ValueError, TypeError):
                pass
    return None


def _get_sms_count(data: dict) -> int | None:
    """Get SMS count (MO + MT) from Simbase API response."""
    current_month = data.get("current_month_usage", {})
    if isinstance(current_month, dict):
        sms_mo = current_month.get("sms_mo", 0) or 0
        sms_mt = current_month.get("sms_mt", 0) or 0
        return sms_mo + sms_mt
    return None


def _get_session_count(data: dict) -> int | None:
    """Get data session count from Simbase API response."""
    current_month = data.get("current_month_usage", {})
    if isinstance(current_month, dict):
        return current_month.get("data_sessions")
    return None


SENSOR_DESCRIPTIONS: tuple[SimbaseSensorEntityDescription, ...] = (
    SimbaseSensorEntityDescription(
        key="data_usage",
        translation_key="data_usage",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_data_usage,
        attr_fn=lambda data: {
            "raw_bytes": data.get("current_month_usage", {}).get("data"),
            "data_sessions": data.get("current_month_usage", {}).get("data_sessions"),
            "total_sessions": data.get("current_month_usage", {}).get("total_sessions"),
        },
    ),
    SimbaseSensorEntityDescription(
        key="status",
        translation_key="sim_status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "enabled",
            "disabled",
            "active",
            "inactive",
            "suspended",
            "terminated",
            "registered",
            "unregistered",
        ],
        value_fn=lambda data: (data.get("state") or data.get("status") or "").lower() or None,
        attr_fn=lambda data: {
            "autodisable": data.get("autodisable"),
            "imei_lock": data.get("imei_lock"),
        },
    ),
    SimbaseSensorEntityDescription(
        key="network",
        translation_key="network",
        icon="mdi:antenna",
        value_fn=lambda data: (data.get("connection") or {}).get("carrier")
        or data.get("network_operator"),
        attr_fn=lambda data: {
            "country": (data.get("connection") or {}).get("country"),
            "mcc": (data.get("connection") or {}).get("mcc"),
            "mnc": (data.get("connection") or {}).get("mnc"),
            "last_update": (data.get("connection") or {}).get("last_update"),
        },
    ),
    SimbaseSensorEntityDescription(
        key="session_status",
        translation_key="session_status",
        icon="mdi:transit-connection-variant",
        device_class=SensorDeviceClass.ENUM,
        options=["in_session", "no_session", "unavailable"],
        value_fn=lambda data: data.get("session_status"),
    ),
    SimbaseSensorEntityDescription(
        key="location",
        translation_key="location",
        icon="mdi:map-marker",
        value_fn=lambda data: (data.get("location") or {}).get("country"),
        attr_fn=lambda data: {
            "carrier": (data.get("location") or {}).get("carrier"),
            "latitude": (data.get("location") or {}).get("lat"),
            "longitude": (data.get("location") or {}).get("lon"),
            "cell_id": (data.get("location") or {}).get("cell_id"),
            "lac": (data.get("location") or {}).get("lac"),
            "radio": (data.get("location") or {}).get("radio"),
            "last_update": (data.get("location") or {}).get("last_update"),
        },
    ),
    SimbaseSensorEntityDescription(
        key="ip_address",
        translation_key="ip_address",
        value_fn=lambda data: data.get("public_ip") or data.get("private_network_ip"),
        attr_fn=lambda data: {
            "public_ip": data.get("public_ip"),
            "private_network_ip": data.get("private_network_ip"),
        },
    ),
    SimbaseSensorEntityDescription(
        key="iccid",
        translation_key="iccid",
        icon="mdi:sim",
        value_fn=lambda data: data.get("iccid") or data.get("ICCID"),
    ),
    SimbaseSensorEntityDescription(
        key="imei",
        translation_key="imei",
        value_fn=lambda data: data.get("imei"),
        attr_fn=lambda data: {
            "imei_lock": data.get("imei_lock"),
            "hardware": data.get("hardware"),
        },
        entity_registry_enabled_default=False,
    ),
    SimbaseSensorEntityDescription(
        key="msisdn",
        translation_key="msisdn",
        value_fn=lambda data: data.get("msisdn"),
        entity_registry_enabled_default=False,
    ),
    SimbaseSensorEntityDescription(
        key="plan",
        translation_key="plan",
        value_fn=lambda data: data.get("coverage"),
        attr_fn=lambda data: {
            "plan_id": data.get("plan_id"),
            "sim_profile": data.get("sim_profile"),
        },
    ),
    # Additional useful sensors based on actual API data
    SimbaseSensorEntityDescription(
        key="monthly_cost",
        translation_key="monthly_cost",
        native_unit_of_measurement="$",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=_get_data_cost,
        attr_fn=lambda data: {
            "data_cost": data.get("current_month_costs", {}).get("data"),
            "sms_cost": data.get("current_month_costs", {}).get("sms"),
            "line_rental": data.get("current_month_costs", {}).get("line_rental"),
        },
    ),
    SimbaseSensorEntityDescription(
        key="sms_count",
        translation_key="sms_count",
        native_unit_of_measurement="messages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:message-text",
        value_fn=_get_sms_count,
        attr_fn=lambda data: {
            "sms_sent": data.get("current_month_usage", {}).get("sms_mo"),
            "sms_received": data.get("current_month_usage", {}).get("sms_mt"),
        },
    ),
    SimbaseSensorEntityDescription(
        key="sms_sent",
        translation_key="sms_sent",
        native_unit_of_measurement="messages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:message-arrow-right",
        value_fn=lambda data: data.get("current_month_usage", {}).get("sms_mo") or 0,
    ),
    SimbaseSensorEntityDescription(
        key="sms_received",
        translation_key="sms_received",
        native_unit_of_measurement="messages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:message-arrow-left",
        value_fn=lambda data: data.get("current_month_usage", {}).get("sms_mt") or 0,
    ),
    SimbaseSensorEntityDescription(
        key="hardware",
        translation_key="hardware",
        value_fn=lambda data: data.get("hardware"),
    ),
)


ACCOUNT_SENSOR_DESCRIPTIONS: tuple[SimbaseSensorEntityDescription, ...] = (
    SimbaseSensorEntityDescription(
        key="account_balance",
        translation_key="account_balance",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda data: _to_float(data.get("balance")),
        attr_fn=lambda data: {
            "currency": data.get("currency", "USD"),
            "auto_top_up_enabled": data.get("auto_top_up_enabled"),
            "auto_top_up_threshold": data.get("auto_top_up_threshold"),
            "auto_top_up_amount": data.get("auto_top_up_amount"),
            "last_update": data.get("last_update"),
        },
    ),
    SimbaseSensorEntityDescription(
        key="total_sims",
        translation_key="total_sims",
        native_unit_of_measurement="SIMs",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("count", 0),
    ),
    SimbaseSensorEntityDescription(
        key="active_sims",
        translation_key="active_sims",
        native_unit_of_measurement="SIMs",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("active_sims", 0),
    ),
    SimbaseSensorEntityDescription(
        key="inactive_sims",
        translation_key="inactive_sims",
        native_unit_of_measurement="SIMs",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("inactive_sims", 0),
    ),
    SimbaseSensorEntityDescription(
        key="total_data_usage",
        translation_key="total_data_usage",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.get("data_usage_mb", 0),
        attr_fn=lambda data: {
            "raw_bytes": data.get("data_usage_bytes"),
        },
    ),
    SimbaseSensorEntityDescription(
        key="total_monthly_cost",
        translation_key="total_monthly_cost",
        native_unit_of_measurement="$",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("total_cost", 0),
    ),
    SimbaseSensorEntityDescription(
        key="total_sms_sent",
        translation_key="total_sms_sent",
        native_unit_of_measurement="messages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:message-arrow-right",
        value_fn=lambda data: data.get("sms_sent", 0),
    ),
    SimbaseSensorEntityDescription(
        key="total_sms_received",
        translation_key="total_sms_received",
        native_unit_of_measurement="messages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:message-arrow-left",
        value_fn=lambda data: data.get("sms_received", 0),
    ),
    SimbaseSensorEntityDescription(
        key="total_sms",
        translation_key="total_sms",
        native_unit_of_measurement="messages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:message-text",
        value_fn=lambda data: data.get("sms_total", 0),
        attr_fn=lambda data: {
            "sent": data.get("sms_sent", 0),
            "received": data.get("sms_received", 0),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Simbase sensors based on a config entry."""
    coordinator: SimbaseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    # Get enabled sensors from options
    enabled_sensors = entry.options.get(CONF_ENABLE_SENSORS, DEFAULT_SENSORS)

    entities: list[SensorEntity] = []

    # Add SIM card sensors
    for iccid in coordinator.get_all_simcards():
        for description in SENSOR_DESCRIPTIONS:
            if description.key in enabled_sensors:
                entities.append(SimbaseSensor(coordinator, iccid, description))

    # Add account-level sensors
    entities.append(SimbaseAccountSensor(
        coordinator, entry.entry_id, ACCOUNT_SENSOR_DESCRIPTIONS[0]
    ))
    for description in ACCOUNT_SENSOR_DESCRIPTIONS[1:]:
        entities.append(SimbaseAccountSensor(coordinator, entry.entry_id, description))

    async_add_entities(entities)


class SimbaseSensor(SimbaseEntity, SensorEntity):
    """Representation of a Simbase sensor."""

    entity_description: SimbaseSensorEntityDescription

    def __init__(
        self,
        coordinator: SimbaseDataUpdateCoordinator,
        iccid: str,
        description: SimbaseSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, iccid)
        self.entity_description = description
        self._attr_unique_id = f"{iccid}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        sim_data = self._get_sim_data()
        return self.entity_description.value_fn(sim_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes."""
        if self.entity_description.attr_fn is None:
            return None
        sim_data = self._get_sim_data()
        attrs = self.entity_description.attr_fn(sim_data)
        attrs["iccid"] = self._iccid
        return attrs


class SimbaseAccountSensor(SimbaseAccountEntity, SensorEntity):
    """Representation of a Simbase account sensor."""

    entity_description: SimbaseSensorEntityDescription

    def __init__(
        self,
        coordinator: SimbaseDataUpdateCoordinator,
        entry_id: str,
        description: SimbaseSensorEntityDescription,
    ) -> None:
        """Initialize the account sensor."""
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"account_{entry_id}_{description.key}"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit, using the live currency for the balance sensor."""
        if self.entity_description.key == "account_balance":
            return self._get_balance_data().get("currency") or "USD"
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        # For balance sensor, use balance data
        if self.entity_description.key == "account_balance":
            balance_data = self._get_balance_data()
            return self.entity_description.value_fn(balance_data)
        # For count sensors, use coordinator data
        if self.entity_description.key == "total_sims":
            return self.coordinator.data.get("count", 0) if self.coordinator.data else 0
        # For other sensors, use totals data
        totals = self._get_totals()
        return self.entity_description.value_fn(totals)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes."""
        if self.entity_description.attr_fn is None:
            return None
        if self.entity_description.key == "account_balance":
            data = self._get_balance_data()
        else:
            data = self._get_totals()
        return self.entity_description.attr_fn(data)
