from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.adaptive_alerting.const import (
    CONF_LEARNING_WINDOW_DAYS,
    CONF_SENSITIVITY,
    CONF_SENSOR_ENTITY_ID,
    DOMAIN,
)


@pytest.fixture(autouse=True)
async def setup_fixtures(recorder_mock, enable_custom_integrations):
    """adaptive_alerting declares recorder as a hard dependency, so the
    config flow needs an in-memory recorder instance available, and
    enable_custom_integrations lets the test loader see our component.
    recorder_mock must be requested before enable_custom_integrations
    touches `hass`, or pytest-homeassistant-custom-component's internal
    "hass already set up" assertion trips.
    """
    yield


async def _start_flow(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_form_shown(hass: HomeAssistant):
    result = await _start_flow(hass)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_valid_numeric_sensor_creates_entry(hass: HomeAssistant):
    hass.states.async_set("sensor.dining_room_humidity", "42.5")

    result = await _start_flow(hass)
    with patch(
        "custom_components.adaptive_alerting.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SENSOR_ENTITY_ID: "sensor.dining_room_humidity",
                CONF_LEARNING_WINDOW_DAYS: 14,
                CONF_SENSITIVITY: 2.5,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Alerting: sensor.dining_room_humidity"
    assert result["data"][CONF_SENSOR_ENTITY_ID] == "sensor.dining_room_humidity"


async def test_non_numeric_sensor_shows_error(hass: HomeAssistant):
    hass.states.async_set("sensor.front_door_lock", "locked")

    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SENSOR_ENTITY_ID: "sensor.front_door_lock",
            CONF_LEARNING_WINDOW_DAYS: 14,
            CONF_SENSITIVITY: 2.5,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_SENSOR_ENTITY_ID: "not_numeric"}


async def test_duplicate_sensor_aborts(hass: HomeAssistant, mock_config_entry_factory):
    hass.states.async_set("sensor.dining_room_humidity", "42.5")
    mock_config_entry_factory(
        unique_id="sensor.dining_room_humidity",
        data={CONF_SENSOR_ENTITY_ID: "sensor.dining_room_humidity"},
    )

    result = await _start_flow(hass)
    with patch(
        "custom_components.adaptive_alerting.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SENSOR_ENTITY_ID: "sensor.dining_room_humidity",
                CONF_LEARNING_WINDOW_DAYS: 14,
                CONF_SENSITIVITY: 2.5,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.fixture
def mock_config_entry_factory(hass: HomeAssistant):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    created = []

    def _factory(**kwargs):
        entry = MockConfigEntry(domain=DOMAIN, **kwargs)
        entry.add_to_hass(hass)
        created.append(entry)
        return entry

    return _factory
