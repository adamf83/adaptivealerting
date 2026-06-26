from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([AdaptiveAlertingZScoreSensor(hass, entry)])


class AdaptiveAlertingZScoreSensor(SensorEntity):
    _attr_should_poll = False
    _attr_native_unit_of_measurement = "σ"
    _attr_icon = "mdi:chart-bell-curve"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_zscore"
        self._attr_name = f"{entry.title} Z-Score"
        self._value = 0.0

    async def async_added_to_hass(self) -> None:
        @callback
        def _update(_event):
            data = self.hass.data[DOMAIN].get(self._entry.entry_id, {})
            result = data.get("result", {})
            self._value = result.get("z_score", 0.0)
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_updated_{self._entry.entry_id}", _update
            )
        )

    @property
    def native_value(self) -> float:
        return self._value
