from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SENSOR_ENTITY_ID, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([AdaptiveAlertingBinarySensor(hass, entry)])


class AdaptiveAlertingBinarySensor(BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_anomaly"
        self._attr_name = f"{entry.title} Anomaly"
        self._state = False
        self._result = {}

    async def async_added_to_hass(self) -> None:
        @callback
        def _update(_event):
            data = self.hass.data[DOMAIN].get(self._entry.entry_id, {})
            self._result = data.get("result", {})
            self._state = self._result.get("is_anomaly", False)
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_updated_{self._entry.entry_id}", _update
            )
        )

    @property
    def is_on(self) -> bool:
        return self._state

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "z_score": self._result.get("z_score"),
            "mean": self._result.get("mean"),
            "std_dev": self._result.get("std_dev"),
            "model_ready": self._result.get("is_ready", False),
            "monitored_entity": self._entry.data.get(CONF_SENSOR_ENTITY_ID),
        }
