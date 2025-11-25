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
"""Sensor platform for Pulsarr Enhanced Requests."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from typing import Any

from . import DOMAIN, PulsarrDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pulsarr Enhanced Requests sensor from a config entry."""
    coordinator: PulsarrDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        PulsarrRequestsSensor(coordinator),
    ])

class PulsarrRequestsSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pulsarr Enhanced Requests sensor."""

    def __init__(self, coordinator: PulsarrDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "Pulsarr Enhanced Requests"
        self._attr_unique_id = f"{coordinator.host}-{coordinator.port}-enhanced-requests"
        self._attr_native_unit_of_measurement = None
        self._attr_icon = "mdi:bell-badge"

    @property
    def native_value(self) -> int:
        """Return the total number of pending requests."""
        # The state value comes directly from the coordinator's data
        return self.coordinator.data.get("total_pending", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes by simplifying the request details."""
        # The full list of enhanced pending requests
        requests_details = self.coordinator.data.get("pending_requests_details", [])
        
        # We must restructure the list into a simple dictionary structure
        # for Home Assistant to display correctly as an attribute.
        simplified_requests = []
        for req in requests_details:
            # Safely access the enriched metadata, falling back to an empty dict if missing
            metadata = req.get('tmdb_metadata', {})
            
            # Use sensible fallbacks for all fields to ensure no items are skipped
            simplified_requests.append({
                "id": req.get("id"),
                
                # CORRECTED LINE: Using 'userName' instead of 'requestedBy'
                "requested_by": req.get("userName") or "Unknown User",
                
                "media_type": metadata.get("media_type") or "unknown",
                
                # Prioritize enriched metadata, but fall back to the original request name
                "title": metadata.get("title") or req.get("name") or req.get("contentTitle") or "Unknown Title", 
                
                "poster_path": metadata.get("poster_path"),
                "overview": metadata.get("overview", "No description available.").split('.')[0] + "...", # Truncate overview for attribute display
                "release_date": metadata.get("release_date"),
                "rating": metadata.get("rating"),
            })
        
        # The key name for the attribute should be descriptive
        return {
            "pending_requests": simplified_requests
        }
