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
# File: custom_components/pulsarr_enhanced_requests/sensor.py
"""Sensor platform for Pulsarr Enhanced Requests."""
from __future__ import annotations

import json

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
        self._attr_native_unit_of_measurement = None # Changed to None to remove unit
        self._attr_icon = "mdi:bell-badge" # You can choose a suitable icon

    @property
    def native_value(self) -> int:
        """Return the total number of pending requests."""
        return self.coordinator.data.get("total_pending", 0)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        # The full list of enhanced pending requests
        return {
            "pending_requests_details": self.coordinator.data.get("pending_requests", [])
        }
