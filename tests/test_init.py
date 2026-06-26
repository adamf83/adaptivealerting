import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adaptive_alerting.const import (
    CONF_LEARNING_WINDOW_DAYS,
    CONF_SENSITIVITY,
    CONF_SENSOR_ENTITY_ID,
    DOMAIN,
    EVENT_ANOMALY_DETECTED,
)


@pytest.fixture(autouse=True)
async def setup_fixtures(recorder_mock, enable_custom_integrations):
    """adaptive_alerting declares recorder as a hard dependency, so setup
    needs an in-memory recorder instance available, and
    enable_custom_integrations lets the test loader see our component.
    recorder_mock must be requested before enable_custom_integrations
    touches `hass`, or pytest-homeassistant-custom-component's internal
    "hass already set up" assertion trips.
    """
    yield


def _make_entry(hass: HomeAssistant, entity_id: str, sensitivity: float = 2.0):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=entity_id,
        title=f"Alerting: {entity_id}",
        data={
            CONF_SENSOR_ENTITY_ID: entity_id,
            CONF_LEARNING_WINDOW_DAYS: 14,
            CONF_SENSITIVITY: sensitivity,
        },
    )
    entry.add_to_hass(hass)
    return entry


async def _feed_normal_samples(hass, entity_id, count=30, value=10.0):
    """Feeds samples that jitter slightly around `value`.

    hass.states.async_set() is a no-op (fires no state_changed event) when
    the new state/attributes are identical to the current ones, so
    force_update=True is needed to drive the component's state-change
    listener on every call. A constant value would also give the baseline
    a std_dev of exactly 0, which forces z_score to 0 by design (see
    test_anomaly_threshold_boundary) and would make every later value look
    non-anomalous -- so a small alternating jitter is used instead to give
    the baseline a realistic, non-zero spread.
    """
    for i in range(count):
        jitter = 0.5 if i % 2 == 0 else -0.5
        hass.states.async_set(entity_id, str(value + jitter), force_update=True)
        await hass.async_block_till_done()


async def test_setup_creates_both_entities(hass: HomeAssistant):
    hass.states.async_set("sensor.temp", "10.0")
    entry = _make_entry(hass, "sensor.temp")

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.alerting_sensor_temp_anomaly") is not None
    assert hass.states.get("sensor.alerting_sensor_temp_z_score") is not None


async def test_anomaly_flips_binary_sensor_and_fires_event(hass: HomeAssistant):
    entity_id = "sensor.temp"
    hass.states.async_set(entity_id, "10.0")
    entry = _make_entry(hass, entity_id, sensitivity=2.0)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await _feed_normal_samples(hass, entity_id, count=30, value=10.0)

    binary_sensor_id = "binary_sensor.alerting_sensor_temp_anomaly"
    assert hass.states.get(binary_sensor_id).state == "off"

    events = []
    hass.bus.async_listen(EVENT_ANOMALY_DETECTED, lambda e: events.append(e))

    hass.states.async_set(entity_id, "10000.0")
    await hass.async_block_till_done()

    assert hass.states.get(binary_sensor_id).state == "on"
    assert len(events) == 1
    assert events[0].data["entity_id"] == entity_id
    assert events[0].data["value"] == 10000.0


async def test_reset_baseline_service_defaults_to_all_entries(hass: HomeAssistant):
    # Setting up the first config entry for a domain bootstraps the whole
    # component, which in turn auto-loads every other entry already added
    # to hass for that domain. So entry_b must be added *after* entry_a is
    # set up, otherwise the explicit setup call below trips
    # OperationNotAllowed("already loaded").
    entry_a = _make_entry(hass, "sensor.temp_a")
    hass.states.async_set("sensor.temp_a", "10.0")
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    entry_b = _make_entry(hass, "sensor.temp_b")
    hass.states.async_set("sensor.temp_b", "20.0")
    assert await hass.config_entries.async_setup(entry_b.entry_id)
    await hass.async_block_till_done()

    await _feed_normal_samples(hass, "sensor.temp_a", count=30, value=10.0)
    await _feed_normal_samples(hass, "sensor.temp_b", count=30, value=20.0)

    model_a = hass.data[DOMAIN][entry_a.entry_id]["model"]
    model_b = hass.data[DOMAIN][entry_b.entry_id]["model"]
    assert model_a.is_ready is True
    assert model_b.is_ready is True

    # No entry_id specified -> the fix means BOTH entries get reset, not just
    # whichever entry happened to register the service first.
    await hass.services.async_call(DOMAIN, "reset_baseline", {}, blocking=True)
    await hass.async_block_till_done()

    assert model_a.is_ready is False
    assert model_b.is_ready is False


async def test_reset_baseline_service_targets_single_entry(hass: HomeAssistant):
    # See comment in test_reset_baseline_service_defaults_to_all_entries:
    # entry_b must be added only after entry_a's setup bootstraps the
    # component, or its explicit setup call below raises
    # OperationNotAllowed("already loaded").
    entry_a = _make_entry(hass, "sensor.temp_a")
    hass.states.async_set("sensor.temp_a", "10.0")
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    entry_b = _make_entry(hass, "sensor.temp_b")
    hass.states.async_set("sensor.temp_b", "20.0")
    assert await hass.config_entries.async_setup(entry_b.entry_id)
    await hass.async_block_till_done()

    await _feed_normal_samples(hass, "sensor.temp_a", count=30, value=10.0)
    await _feed_normal_samples(hass, "sensor.temp_b", count=30, value=20.0)

    model_a = hass.data[DOMAIN][entry_a.entry_id]["model"]
    model_b = hass.data[DOMAIN][entry_b.entry_id]["model"]

    await hass.services.async_call(
        DOMAIN, "reset_baseline", {"entry_id": entry_a.entry_id}, blocking=True
    )
    await hass.async_block_till_done()

    assert model_a.is_ready is False
    assert model_b.is_ready is True


async def test_persistence_throttle_uses_update_counter_not_capped_sample_count(
    hass: HomeAssistant,
):
    """Regression test for the disk-write-storm bug: the persistence
    throttle must be driven by a plain update counter, not by
    `model.sample_count`, which plateaus once the deque hits MAX_SAMPLES
    and would otherwise make every single update trigger a save."""
    entity_id = "sensor.temp"
    hass.states.async_set(entity_id, "10.0")
    entry = _make_entry(hass, entity_id)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    model = hass.data[DOMAIN][entry.entry_id]["model"]
    model.reset()  # discard whatever recorder history seeding may have added
    model._samples.extend([10.0] * (model._samples.maxlen - 1))
    model._is_ready = True
    assert model.sample_count == model._samples.maxlen - 1

    save_calls = []
    store = hass.data[DOMAIN][entry.entry_id]["store"]
    original_save = store.async_save

    async def _tracked_save(data):
        save_calls.append(data)
        return await original_save(data)

    store.async_save = _tracked_save

    # Push the deque to its cap, then beyond it, well past one throttle
    # window (50 updates). Pre-fix, every update past the cap would save.
    for _ in range(60):
        hass.states.async_set(entity_id, "11.0", force_update=True)
        await hass.async_block_till_done()

    assert model.sample_count == model._samples.maxlen
    assert len(save_calls) <= 2
