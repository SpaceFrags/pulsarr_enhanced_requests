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
# File: custom_components/pulsarr_enhanced_requests/__init__.py
from __future__ import annotations # THIS MUST BE THE VERY FIRST EXECUTABLE LINE

"""The Pulsarr Enhanced Requests integration."""

import asyncio
import logging
from datetime import timedelta
import aiohttp
import voluptuous as vol # Import voluptuous for service schema validation
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv # Import config_validation for service schema

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError # Ensure HomeAssistantError is imported

_LOGGER = logging.getLogger(__name__)

DOMAIN = "pulsarr_enhanced_requests"
PLATFORMS = ["sensor"]

# Service Definitions
SERVICE_PROCESS_REQUEST = "process_request"

SERVICE_PROCESS_REQUEST_SCHEMA = vol.Schema({
    vol.Required("request_id"): cv.string,
    vol.Required("action"): vol.In(["approve", "reject"]),
})

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pulsarr Enhanced Requests from a config entry."""
    _LOGGER.info("Pulsarr Enhanced Requests integration is starting up!")
    hass.data.setdefault(DOMAIN, {})

    # Create a coordinator to fetch data from Pulsarr
    coordinator = PulsarrDataUpdateCoordinator(hass, entry.data["host"], entry.data["port"], entry.data["api_key"])
    
    # Perform initial fetch, raising ConfigEntryNotReady if it fails
    # This is also where the warnings about async_config_entry_first_refresh originate.
    # It's a valid pattern for now, but HA is moving away from it for config flow validation.
    # The integration will still function.
    await coordinator.async_config_entry_first_refresh() 

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    _register_services(hass, coordinator)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        # Unregister services when unloading
        hass.services.async_remove(DOMAIN, SERVICE_PROCESS_REQUEST)
    return unload_ok

# Moved PulsarrDataUpdateCoordinator definition above _register_services
class PulsarrDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Pulsarr API."""

    def __init__(self, hass: HomeAssistant, host: str, port: str, api_key: str):
        """Initialize."""
        self.host = host
        self.port = port
        self.api_key = api_key
        # Base URL is now /v1 based on updated Pulsarr API documentation
        self.base_url = f"http://{host}:{port}/v1" 
        
        # New debug log to check the API key value
        _LOGGER.debug("Initializing coordinator. API key received: '%s'", self.api_key)
        
        # Conditionally set headers based on API key presence
        self.headers = {"Content-Type": "application/json"}
        if self.api_key: # Only add X-Api-Key if it's not an empty string
            self.headers["X-Api-Key"] = self.api_key
            _LOGGER.debug("API key loaded successfully. Headers will include X-Api-Key.")
        else:
            _LOGGER.warning("API key is not configured. API requests may fail.")

        self.hass = hass
        # Obtain the Home Assistant managed aiohttp ClientSession once
        self.websession = async_get_clientsession(hass)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5), # Update every 5 minutes
        )

    async def _async_update_data(self):
        """Fetch data from Pulsarr API."""
        try:
            # 1. Fetch all approval requests
            # Endpoint path is /approval/requests as per updated documentation
            approval_requests_url = f"{self.base_url}/approval/requests" 
            _LOGGER.debug("Fetching approval requests from: %s with headers: %s", approval_requests_url, self.headers) # Added headers to debug log
            # Use self.websession directly, no 'async with' here as it's managed by HA
            async with self.websession.get(approval_requests_url, headers=self.headers) as response:
                response.raise_for_status()
                all_requests = await response.json()

            if not all_requests or "approvalRequests" not in all_requests:
                _LOGGER.warning("Pulsarr API did not return expected 'approvalRequests' data.")
                # Return empty data, but don't raise UpdateFailed unless it's a critical error
                return {"pending_requests": [], "total_pending": 0}

            pending_requests = [
                req for req in all_requests["approvalRequests"] if req.get("status") == "pending"
            ]

            enhanced_pending_requests = []
            for req in pending_requests:
                request_details = {
                    "id": req.get("id"),
                    "userName": req.get("userName"),
                    "contentType": req.get("contentType"),
                    "contentTitle": req.get("contentTitle"),
                    "contentGuids": req.get("contentGuids", []),
                    "tmdb_metadata": {} # Placeholder for TMDB metadata
                }

                # 2. Fetch TMDB metadata for each contentGuid
                for guid in request_details["contentGuids"]:
                    if guid.startswith("tmdb:"):
                        # Pulsarr's /tmdb/metadata/:id endpoint expects the full GUID (e.g., tmdb:400650)
                        tmdb_metadata_url = f"{self.base_url}/tmdb/metadata/{guid}" 
                        _LOGGER.debug("Fetching TMDB metadata for GUID %s from: %s", guid, tmdb_metadata_url)
                        # Use self.websession directly, no 'async with' here as it's managed by HA
                        async with self.websession.get(tmdb_metadata_url, headers=self.headers) as tmdb_response:
                            if tmdb_response.status == 200:
                                tmdb_data = await tmdb_response.json()
                                # THIS IS THE KEY DEBUG LOG:
                                _LOGGER.debug("Successfully fetched TMDB metadata for GUID %s. Response: %s", guid, tmdb_data)
                                
                                # Access nested fields based on the provided JSON structure
                                metadata_details = tmdb_data.get("metadata", {}).get("details", {})
                                radarr_ratings = tmdb_data.get("radarrRatings", {})

                                request_details["tmdb_metadata"][guid] = {
                                    "poster_path": metadata_details.get("poster_path"),
                                    "backdrop_path": metadata_details.get("backdrop_path"),
                                    # Correctly access the 'value' from nested rating objects
                                    "tmdb_ratings": radarr_ratings.get("tmdb", {}).get("value"),
                                    "imdb_ratings": radarr_ratings.get("imdb", {}).get("value"),
                                    "rottenTomatoes_ratings": radarr_ratings.get("rottenTomatoes", {}).get("value")
                                }
                            else:
                                _LOGGER.warning(
                                    "Failed to fetch TMDB metadata for GUID %s. Status: %s. Response: %s",
                                    guid, tmdb_response.status, await tmdb_response.text() # Log full response for debugging
                                )
                                request_details["tmdb_metadata"][guid] = {"error": f"Status {tmdb_response.status}"}
                    # Add logic for other GUID types if needed (e.g., tvdb)
                enhanced_pending_requests.append(request_details)

            _LOGGER.debug("Fetched %d pending requests with enhanced details.", len(enhanced_pending_requests))
            return {
                "pending_requests": enhanced_pending_requests,
                "total_pending": len(enhanced_pending_requests)
            }

        except aiohttp.ClientError as err:
            # Raise ConfigEntryNotReady during initial setup if API is unreachable
            if self.data is None: # Check if this is the first data fetch
                raise ConfigEntryNotReady(f"Pulsarr API is unreachable during setup: {err}") from err
            raise UpdateFailed(f"Error communicating with Pulsarr API: {err}") from err
        except asyncio.TimeoutError as err:
            if self.data is None:
                raise ConfigEntryNotReady(f"Timeout while communicating with Pulsarr API during setup: {err}") from err
            raise UpdateFailed(f"Timeout while communicating with Pulsarr API: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching Pulsarr data.")
            if self.data is None:
                raise ConfigEntryNotReady(f"Unexpected error during Pulsarr setup: {err}") from err
            raise UpdateFailed(f"Unexpected error: {err}") from err

@callback
def _register_services(hass: HomeAssistant, coordinator: PulsarrDataUpdateCoordinator) -> None:
    """Register the services for the integration."""

    async def handle_process_request(call):
        """Handle the service call to approve or reject a request."""
        request_id = call.data.get("request_id")
        action = call.data.get("action")
        
        _LOGGER.debug("Processing request %s with action %s", request_id, action)

        # Map the 'approve'/'reject' action to 'approved'/'rejected' for Pulsarr API
        pulsarr_status = "approved" if action == "approve" else "rejected"
        
        try:
            request_url = f"{coordinator.base_url}/approval/requests/{request_id}"
            payload = {"status": pulsarr_status}

            # Use coordinator.websession directly with PATCH method
            async with coordinator.websession.patch(request_url, headers=coordinator.headers, json=payload) as response:
                response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
                _LOGGER.info("Successfully processed request %s with action %s. Response: %s", request_id, action, await response.text())
                # After successful action, force an update of the sensor data
                await coordinator.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error("Error processing request %s: %s", request_id, err)
            raise HomeAssistantError(f"Error communicating with Pulsarr API: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error processing request %s", request_id)
            raise HomeAssistantError(f"Unexpected error: {err}") from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_PROCESS_REQUEST,
        handle_process_request,
        schema=SERVICE_PROCESS_REQUEST_SCHEMA,
    )
