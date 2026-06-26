from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .baseline_model import BaselineModel
from .const import (
    CONF_LEARNING_WINDOW_DAYS,
    CONF_SENSOR_ENTITY_ID,
    CONF_SENSITIVITY,
    DEFAULT_LEARNING_WINDOW_DAYS,
    DEFAULT_SENSITIVITY,
    DOMAIN,
    EVENT_ANOMALY_DETECTED,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    # Load persisted baseline from storage
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
    stored = await store.async_load()

    sensitivity = entry.options.get(
        CONF_SENSITIVITY, entry.data.get(CONF_SENSITIVITY, DEFAULT_SENSITIVITY)
    )

    if stored:
        model = BaselineModel.from_dict(stored)
        model.sensitivity = float(sensitivity)
    else:
        model = BaselineModel(sensitivity=float(sensitivity))

    hass.data[DOMAIN][entry.entry_id] = {
        "model": model,
        "store": store,
        "config": entry.data,
        "result": {},
    }

    # Seed the model from recorder history on startup
    await _seed_from_history(hass, entry, model)

    # Subscribe to live state changes
    monitored_entity = entry.data[CONF_SENSOR_ENTITY_ID]
    update_count = 0

    async def _state_changed(event):
        nonlocal update_count

        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unavailable", "unknown"):
            return
        try:
            value = float(new_state.state)
        except ValueError:
            return

        result = model.evaluate(value)
        model.add_sample(value)
        update_count += 1

        # Persist updated model every 50 samples
        if update_count % 50 == 0:
            await store.async_save(model.to_dict())

        hass.data[DOMAIN][entry.entry_id]["result"] = result

        # Fire HA event on anomaly
        if result["is_anomaly"]:
            hass.bus.async_fire(
                EVENT_ANOMALY_DETECTED,
                {
                    "entity_id": monitored_entity,
                    "value": value,
                    "z_score": result["z_score"],
                    "mean": result["mean"],
                    "std_dev": result["std_dev"],
                },
            )
            _LOGGER.warning(
                "Anomaly detected on %s: value=%.3f z_score=%.3f",
                monitored_entity,
                value,
                result["z_score"],
            )

        # Notify entities to update their state
        hass.bus.async_fire(f"{DOMAIN}_updated_{entry.entry_id}")

    entry.async_on_unload(
        async_track_state_change_event(hass, [monitored_entity], _state_changed)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register reset_baseline service (once, guarded). The handler is kept
    # entry-agnostic so it works correctly regardless of which entry happened
    # to trigger registration first.
    if not hass.services.has_service(DOMAIN, "reset_baseline"):

        async def handle_reset(call: ServiceCall) -> None:
            target_entry_id = call.data.get("entry_id")
            target_ids = (
                [target_entry_id] if target_entry_id else list(hass.data[DOMAIN])
            )
            for target_id in target_ids:
                if target_id in hass.data[DOMAIN]:
                    hass.data[DOMAIN][target_id]["model"].reset()
                    await hass.data[DOMAIN][target_id]["store"].async_save({})
                    _LOGGER.info("Baseline reset for entry %s", target_id)

        hass.services.async_register(DOMAIN, "reset_baseline", handle_reset)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _seed_from_history(
    hass: HomeAssistant, entry: ConfigEntry, model: BaselineModel
) -> None:
    """Pull recent history from the recorder to pre-seed the model."""
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.history import get_significant_states

    entity_id = entry.data[CONF_SENSOR_ENTITY_ID]
    days = entry.data.get(CONF_LEARNING_WINDOW_DAYS, DEFAULT_LEARNING_WINDOW_DAYS)
    start = datetime.now(timezone.utc) - timedelta(days=int(days))

    try:
        instance = get_instance(hass)
        states = await instance.async_add_executor_job(
            get_significant_states,
            hass,
            start,
            None,
            [entity_id],
        )
        for state in states.get(entity_id, []):
            if state.state not in ("unavailable", "unknown"):
                try:
                    model.add_sample(float(state.state))
                except ValueError:
                    pass
        _LOGGER.info(
            "Seeded baseline for %s with %d historical samples",
            entity_id,
            model.sample_count,
        )
    except Exception as err:
        _LOGGER.warning("Could not seed from history: %s", err)
