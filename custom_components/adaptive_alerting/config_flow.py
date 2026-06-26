from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_LEARNING_WINDOW_DAYS,
    CONF_SENSITIVITY,
    CONF_SENSOR_ENTITY_ID,
    DEFAULT_LEARNING_WINDOW_DAYS,
    DEFAULT_SENSITIVITY,
    DOMAIN,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SENSOR_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(
                domain=SENSOR_DOMAIN,  # Only shows entities in the sensor domain
                multiple=False,
            )
        ),
        vol.Optional(
            CONF_LEARNING_WINDOW_DAYS,
            default=DEFAULT_LEARNING_WINDOW_DAYS,
        ): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=90,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="days",
            )
        ),
        vol.Optional(
            CONF_SENSITIVITY,
            default=DEFAULT_SENSITIVITY,
        ): NumberSelector(
            NumberSelectorConfig(
                min=1.0,
                max=5.0,
                step=0.1,
                mode=NumberSelectorMode.SLIDER,
            )
        ),
    }
)


class AdaptiveAlertingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Adaptive Alerting."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            entity_id = user_input[CONF_SENSOR_ENTITY_ID]

            # Prevent duplicate entries for the same sensor
            await self.async_set_unique_id(entity_id)
            self._abort_if_unique_id_configured()

            # Validate the selected entity has a numeric state
            state = self.hass.states.get(entity_id)
            if state is None:
                errors[CONF_SENSOR_ENTITY_ID] = "entity_not_found"
            else:
                try:
                    float(state.state)
                except (ValueError, TypeError):
                    if state.state not in ("unavailable", "unknown"):
                        errors[CONF_SENSOR_ENTITY_ID] = "not_numeric"

            if not errors:
                # Use the entity's friendly name in the entry title
                entity_registry = er.async_get(self.hass)
                entry = entity_registry.async_get(entity_id)
                friendly_name = (
                    entry.name or entry.original_name
                    if entry
                    else entity_id
                )
                return self.async_create_entry(
                    title=f"Alerting: {friendly_name}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )
