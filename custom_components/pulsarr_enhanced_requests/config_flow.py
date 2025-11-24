# Copyright 2024 SpaceFrags
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# File: custom_components/pulsarr_enhanced_requests/config_flow.py
"""Config flow for Pulsarr Enhanced Requests integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError, ConfigEntryNotReady 

from . import DOMAIN, PulsarrDataUpdateCoordinator 

_LOGGER = logging.getLogger(__name__)

# Define schema for user input
# FIX 1: API Key is now REQUIRED as requested.
DATA_SCHEMA = vol.Schema({
    vol.Required("host"): str,
    vol.Required("port", default=7000): int, 
    vol.Required("api_key"): str, 
})

class PulsarrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pulsarr Enhanced Requests."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            host = user_input["host"]
            port = user_input["port"]
            api_key = user_input["api_key"]

            # Validate input by trying to connect to Pulsarr
            try:
                info = await self._async_validate_input(host, port, api_key)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception: # Catch any other unexpected errors during validation
                _LOGGER.exception("Unexpected exception during config flow validation")
                errors["base"] = "unknown"
            else:
                # If validation is successful, create the config entry
                return self.async_create_entry(title=info["title"], data=user_input)

        # FIX 2: We use the simple DATA_SCHEMA since the API key is now required.
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def _async_validate_input(self, host: str, port: int, api_key: str) -> dict:
        """Validate the user input allows us to connect to Pulsarr."""
        coordinator = PulsarrDataUpdateCoordinator(self.hass, host, port, api_key)
        
        try:
            # FIX 3: Call the internal data update method directly instead of the 
            # lifecycle method 'async_config_entry_first_refresh', which caused the error.
            await coordinator._async_update_data() 
            
        except ConfigEntryNotReady as err:
            if "unreachable" in str(err).lower() or "timeout" in str(err).lower():
                raise CannotConnect from err
            if "unauthorized" in str(err).lower() or "forbidden" in str(err).lower():
                raise InvalidAuth from err
            raise HomeAssistantError(f"Unexpected error during validation: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error during validation of Pulsarr connection")
            # If the error is the specific ConfigEntryError we saw, re-raise it properly
            if "config entry" in str(err).lower():
                # We can remove this block now, as the fix above should prevent the error
                _LOGGER.warning("ConfigEntryError detected during validation, ignoring as it's likely due to HA versioning.")
            raise HomeAssistantError(f"Unknown error during validation: {err}") from err

        # Return info that will be used as the title of the integration entry
        return {"title": f"Pulsarr ({host}:{port})"}


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
