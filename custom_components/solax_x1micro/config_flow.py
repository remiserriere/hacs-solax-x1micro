"""Config flow for the SolaX X1-Micro integration."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_INVERTER_TYPE,
    CONF_SERIAL_NUMBER,
    DOMAIN,
    INVERTER_TYPE_X1_MICRO_2IN1,
    INVERTER_TYPES,
)

# Serial numbers seen in the wild: alphanumeric, up to 21 chars (frame field size)
_SN_RE = re.compile(r"^[A-Za-z0-9]{5,21}$")

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_INVERTER_TYPE, default=INVERTER_TYPE_X1_MICRO_2IN1
        ): SelectSelector(
            SelectSelectorConfig(
                options=list(INVERTER_TYPES.keys()),
                mode=SelectSelectorMode.LIST,
                translation_key="inverter_type",
            )
        ),
        vol.Required(CONF_SERIAL_NUMBER): str,
    }
)


class SolaxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SolaX X1-Micro."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            serial_number: str = user_input[CONF_SERIAL_NUMBER].strip()

            if not _SN_RE.match(serial_number):
                errors[CONF_SERIAL_NUMBER] = "invalid_serial"
            else:
                inverter_type: str = user_input[CONF_INVERTER_TYPE]
                inverter_model: str = INVERTER_TYPES.get(inverter_type, inverter_type)

                # Prevent duplicate entries for the same serial number
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"SolaX {inverter_model} ({serial_number})",
                    data={
                        CONF_INVERTER_TYPE: inverter_type,
                        CONF_SERIAL_NUMBER: serial_number,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
