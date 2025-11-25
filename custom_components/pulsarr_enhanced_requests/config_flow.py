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
"""Config flow for Pulsarr Enhanced Requests integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError, ConfigEntryNotReady

from . import DOMAIN, PulsarrDataUpdateCoordinator # Import DOMAIN and Coordinator

_LOGGER = logging.getLogger(__name__)

# Define schema for user input
DATA_SCHEMA = vol.Schema({
    vol.Required("host"): str,
    vol.Required("port", default=3003): int, # Default Pulsarr port
    vol.Required("api_key"): str, # FIXED: API key is now marked as Required
})

async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect.
    
    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    host = data["host"]
    port = data["port"]
    api_key = data["api_key"] # Access key directly, it's guaranteed to exist by the schema

    # Pass individual arguments to the coordinator constructor
    try:
        coordinator = PulsarrDataUpdateCoordinator(hass, host, port, api_key)
        
        # Call the update function directly for validation (previous fix)
        await coordinator._async_update_data()
        
    except ConfigEntryNotReady as err:
        if "unreachable" in str(err).lower() or "timeout" in str(err).lower():
            raise CannotConnect from err
        
        # The key is required, so an empty key is handled here if the user somehow bypassed the form validation,
        # or if the entered key is simply invalid.
        if api_key == "" and ("unauthorized" in str(err).lower() or "forbidden" in str(err).lower()):
            _LOGGER.warning("Pulsarr returned unauthorized/forbidden with empty API key.")
            raise CannotConnect("API key cannot be empty. Authentication is enabled on Pulsarr.") from err
        if "unauthorized" in str(err).lower() or "forbidden" in str(err).lower():
            raise InvalidAuth from err
            
        raise HomeAssistantError(f"Unexpected error during validation: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unexpected error during validation of Pulsarr connection")
        raise HomeAssistantError(f"Unknown error during validation: {err}") from err

    # Return info that will be used as the title of the integration entry
    return {"title": f"Pulsarr ({host}:{port})"}


class PulsarrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pulsarr Enhanced Requests."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Explicitly check for an empty string input for API key, even though 'Required' is set
            if not user_input.get("api_key"):
                 # This sets a field-level error if the API key is empty
                 errors["api_key"] = "required" 
            else:
                try:
                    # The validation function handles the coordinator instantiation using the explicit arguments
                    info = await validate_input(self.hass, user_input)

                    return self.async_create_entry(title=info["title"], data=user_input)
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except Exception: # Catch other exceptions
                    _LOGGER.exception("Unexpected exception in async_step_user")
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
