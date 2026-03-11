"""Config flow for the SolaX X1-Micro integration."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SERIAL_NUMBER, DOMAIN

# Serial numbers seen in the wild: alphanumeric, up to 21 chars (frame field size)
_SN_RE = re.compile(r"^[A-Za-z0-9]{5,21}$")

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
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
                # Prevent duplicate entries for the same serial number
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"SolaX X1-Micro ({serial_number})",
                    data={CONF_SERIAL_NUMBER: serial_number},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
