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
from __future__ import annotations # THIS MUST BE THE VERY FIRST EXECUTABLE LINE

"""The Pulsarr Enhanced Requests integration."""

import asyncio
import logging
from typing import Any
from datetime import timedelta # Import timedelta for specifying the update interval
import aiohttp
import aiohttp.client_exceptions
import voluptuous as vol
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError

_LOGGER = logging.getLogger(__name__)

DOMAIN = "pulsarr_enhanced_requests"
PLATFORMS = ["sensor"]

# --- NEW: Define the desired update interval (e.g., 5 minutes) ---
UPDATE_INTERVAL = timedelta(minutes=5)

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

class PulsarrDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Pulsarr API."""

    def __init__(self, hass: HomeAssistant, host: str, port: int, api_key: str): 
        """Initialize."""
        self.host = host
        self.port = port
        self.api_key = api_key
        # Base URL is just the scheme/host/port
        self.base_url = f"http://{host}:{port}" 
        
        # Conditionally set headers based on API key presence
        self.headers = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["X-Api-Key"] = self.api_key
        
        self.websession = async_get_clientsession(hass)

        # --- FIX APPLIED HERE: Setting the explicit update interval ---
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL, # Use the defined 5 minute interval
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Pulsarr API. This is called automatically by the coordinator."""
        _LOGGER.debug("Starting Pulsarr data update...")
        try:
            # Step 1: Get all pending requests
            requests_url = f"{self.base_url}/v1/approval/requests?status=pending"
            async with self.websession.get(requests_url, headers=self.headers) as response:
                response.raise_for_status()
                full_response = await response.json()
                
                # Extract the 'approvalRequests' array
                pending_requests = full_response.get("approvalRequests", [])
            
            # Step 2: Enrich each request with TMDB/TMDb metadata
            enhanced_requests = []
            valid_requests = [r for r in pending_requests if isinstance(r, dict)]
            
            tasks = [self._async_fetch_tmdb_metadata(request) for request in valid_requests]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    _LOGGER.warning("Failed to fetch TMDB data for one item: %s", result)
                    continue 
                
                if result:
                    enhanced_requests.append(result)

            _LOGGER.debug("Successfully fetched and enhanced %d pending requests.", len(enhanced_requests))
            
            # Return the aggregated data
            return {
                "total_pending": len(enhanced_requests),
                "pending_requests_details": enhanced_requests,
            }

        except aiohttp.ClientConnectorError as err:
            if self.data is None:
                raise ConfigEntryNotReady(f"Connection to Pulsarr failed during setup: {err}") from err
            raise UpdateFailed(f"Connection to Pulsarr failed: {err}") from err
        except aiohttp.ClientResponseError as err:
            if err.status in (401, 403):
                raise UpdateFailed("Invalid API Key or forbidden access.") from err
            raise UpdateFailed(f"Pulsarr API returned error: {err.message}") from err
        except UpdateFailed:
            raise
        except Exception as err:
            _LOGGER.exception("Unexpected error during Pulsarr data update")
            if self.data is None:
                raise ConfigEntryNotReady(f"Unexpected error during Pulsarr setup: {err}") from err
            raise UpdateFailed(f"Unknown error during Pulsarr update: {err}") from err

    async def _async_fetch_tmdb_metadata(self, request: dict) -> dict | None:
        """Fetches TMDB/TMDb metadata for a single request item."""
        
        selected_guid = next((g for g in request.get('contentGuids', []) if g.startswith('tmdb:') or g.startswith('tvdb:')), None)
        
        if not selected_guid:
            return request 

        metadata_url = f"{self.base_url}/v1/tmdb/metadata/{selected_guid}" 
        media_type = 'movie' if selected_guid.startswith('tmdb:') else 'series'

        try:
            # Setting a short timeout for metadata fetch
            async with self.websession.get(metadata_url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                response.raise_for_status()
                
                metadata_response = await response.json()
                
                # Drill down to the actual details object
                metadata = metadata_response.get('metadata', {}).get('details', {})
                
                if not metadata:
                    return request

                # Combine original request data with fetched metadata
                request["tmdb_metadata"] = {
                    "title": metadata.get('title') or metadata.get('name'),
                    "poster_path": metadata.get('poster_path'),
                    "backdrop_path": metadata.get('backdrop_path'),
                    "overview": metadata.get('overview'),
                    "release_date": metadata.get('release_date') or metadata.get('first_air_date'),
                    "rating": metadata.get('vote_average'),
                    "media_type": media_type
                }
                
                return request
        except aiohttp.ClientError as err:
            _LOGGER.warning("Failed to fetch rich metadata for ID %s using URL %s. Error: %s", request.get('id'), metadata_url, err)
            return request
        except Exception as err:
            _LOGGER.exception("Unexpected error during TMDB metadata fetch for ID %s.", request.get('id'))
            return request

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
            # Use the correct Pulsarr API path for the request
            request_url = f"{coordinator.base_url}/v1/approval/requests/{request_id}" 
            payload = {"status": pulsarr_status}

            # Use coordinator.websession directly with PATCH method, setting timeout
            async with coordinator.websession.patch(request_url, headers=coordinator.headers, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
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
