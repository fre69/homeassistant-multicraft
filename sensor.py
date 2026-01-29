"""Sensor platform for Multicraft integration."""

import logging
import asyncio
import socket
import struct
import time
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Convert text to slug format for entity_id."""
    import re
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = text.strip('_')
    return text


SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="status",
        translation_key="status",
        icon="mdi:server",
    ),
    SensorEntityDescription(
        key="onlinePlayers",
        translation_key="online_players",
        icon="mdi:account-multiple",
        native_unit_of_measurement="joueurs",
    ),
    SensorEntityDescription(
        key="maxPlayers",
        translation_key="max_players",
        icon="mdi:account-multiple-outline",
        native_unit_of_measurement="joueurs",
    ),
    SensorEntityDescription(
        key="latency",
        translation_key="latency",
        icon="mdi:speedometer",
        native_unit_of_measurement="ms",
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key="version",
        translation_key="version",
        icon="mdi:information-outline",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Multicraft sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    server_ids = hass.data[DOMAIN][entry.entry_id]["server_ids"]
    servers_info = hass.data[DOMAIN][entry.entry_id]["servers_info"]

    entities = []
    for server_id in server_ids:
        server_name = servers_info.get(server_id, f"Server {server_id}")
        for description in SENSOR_DESCRIPTIONS:
            entities.append(
                MulticraftSensor(coordinator, description, server_id, server_name, entry.entry_id)
            )

    async_add_entities(entities)


class MulticraftSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Multicraft sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        description: SensorEntityDescription,
        server_id: str,
        server_name: str,
        entry_id: str,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._server_id = server_id
        self._server_name = server_name
        self._entry_id = entry_id

        # Slugify server name for entity_id
        server_slug = slugify(server_name)

        # Unique ID
        self._attr_unique_id = f"multicraft_{server_id}_{description.key}"

        # Entity ID will be: sensor.multicraft_{server_name}_{sensor_type}
        self.entity_id = f"sensor.multicraft_{server_slug}_{description.key.lower()}"

        # Display name
        name_map = {
            "status": "Status",
            "onlinePlayers": "Joueurs en ligne",
            "maxPlayers": "Joueurs max",
            "latency": "Latence",
            "version": "Version",
        }
        self._attr_name = name_map.get(description.key, description.key)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_{self._server_id}")},
            name=self._server_name,
            manufacturer="Multicraft",
            model="Minecraft Server",
            sw_version=self._get_version(),
        )

    def _get_version(self) -> str | None:
        """Get server version from coordinator data."""
        if not self.coordinator.data:
            return None
        server_data = self.coordinator.data.get(self._server_id, {})
        return server_data.get("version")

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        server_data = self.coordinator.data.get(self._server_id, {})
        value = server_data.get(self.entity_description.key)

        if value is None:
            return None

        # Convert status to French
        if self.entity_description.key == "status":
            status_map = {
                "online": "En ligne",
                "offline": "Hors ligne",
                "starting": "Démarrage",
                "stopping": "Arrêt",
            }
            return status_map.get(value, value)

        # Convert numeric values to int if they are strings
        if self.entity_description.key in ("onlinePlayers", "maxPlayers", "latency"):
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "server_id": self._server_id,
            "server_name": self._server_name,
        }

        # Add players list if available
        if self.coordinator.data:
            server_data = self.coordinator.data.get(self._server_id, {})
            if "players" in server_data:
                attrs["players"] = server_data.get("players", [])

        return attrs
