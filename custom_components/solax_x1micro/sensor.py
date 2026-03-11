"""Sensor platform for the SolaX X1-Micro integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory

from .const import CONF_SERIAL_NUMBER, DOMAIN
from .coordinator import SolaxCoordinator


@dataclass(frozen=True, kw_only=True)
class SolaxSensorEntityDescription(SensorEntityDescription):
    """Describes a SolaX X1-Micro sensor."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[SolaxSensorEntityDescription, ...] = (
    # ── AC / Grid ────────────────────────────────────────────────────────────
    SolaxSensorEntityDescription(
        key="ac_power",
        name="AC Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("ac_power_W"),
    ),
    SolaxSensorEntityDescription(
        key="grid_voltage",
        name="Grid Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("grid_voltage_V"),
    ),
    SolaxSensorEntityDescription(
        key="grid_current",
        name="Grid Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("grid_current_A"),
    ),
    SolaxSensorEntityDescription(
        key="grid_frequency",
        name="Grid Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("grid_freq_Hz"),
    ),
    # ── PV MPPT1 ─────────────────────────────────────────────────────────────
    SolaxSensorEntityDescription(
        key="vpv1",
        name="PV Voltage MPPT1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("vpv1_V"),
    ),
    SolaxSensorEntityDescription(
        key="ipv1",
        name="PV Current MPPT1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("ipv1_A"),
    ),
    SolaxSensorEntityDescription(
        key="ppv1",
        name="PV Power MPPT1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("ppv1_W"),
    ),
    # ── PV MPPT2 ─────────────────────────────────────────────────────────────
    SolaxSensorEntityDescription(
        key="vpv2",
        name="PV Voltage MPPT2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("vpv2_V"),
    ),
    SolaxSensorEntityDescription(
        key="ipv2",
        name="PV Current MPPT2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("ipv2_A"),
    ),
    SolaxSensorEntityDescription(
        key="ppv2",
        name="PV Power MPPT2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("ppv2_W"),
    ),
    # ── DC Total ─────────────────────────────────────────────────────────────
    SolaxSensorEntityDescription(
        key="pdc_total",
        name="Total DC Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("pdc_total_W"),
    ),
    # ── Energy ───────────────────────────────────────────────────────────────
    SolaxSensorEntityDescription(
        key="e_today",
        name="Energy Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("e_today_kWh"),
    ),
    SolaxSensorEntityDescription(
        key="e_total",
        name="Energy Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("e_total_kWh"),
    ),
    # ── Temperature ──────────────────────────────────────────────────────────
    SolaxSensorEntityDescription(
        key="temperature1",
        name="Temperature 1",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("temperature1_C"),
    ),
    SolaxSensorEntityDescription(
        key="temperature2",
        name="Temperature 2",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("temperature2_C"),
    ),
    # ── Inverter info (diagnostic) ────────────────────────────────────────────
    SolaxSensorEntityDescription(
        key="rated_power",
        name="Rated Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("rated_power_W"),
    ),
    SolaxSensorEntityDescription(
        key="run_mode",
        name="Run Mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("run_mode"),
    ),
    SolaxSensorEntityDescription(
        key="inverter_sn",
        name="Inverter Serial Number",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("inverter_sn"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SolaX X1-Micro sensors from a config entry."""
    coordinator: SolaxCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SolaxSensor(coordinator, description) for description in SENSORS
    )


class SolaxSensor(SensorEntity):
    """Representation of a SolaX X1-Micro sensor."""

    entity_description: SolaxSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolaxCoordinator,
        description: SolaxSensorEntityDescription,
    ) -> None:
        self.entity_description = description
        self._coordinator = coordinator
        serial = coordinator.serial_number
        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=f"SolaX X1-Micro ({serial})",
            manufacturer="SolaX Power",
            model="X1-Micro 2 in 1",
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self._coordinator.data)

    @property
    def available(self) -> bool:
        return self._coordinator.online

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_update)
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
