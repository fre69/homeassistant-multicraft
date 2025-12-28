"""Switch platform for Multicraft integration."""

import logging
import re
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Convert text to slug format for entity_id."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = text.strip('_')
    return text


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Multicraft switch platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    server_ids = hass.data[DOMAIN][entry.entry_id]["server_ids"]
    servers_info = hass.data[DOMAIN][entry.entry_id]["servers_info"]

    entities = []
    for server_id in server_ids:
        server_name = servers_info.get(server_id, f"Server {server_id}")
        entities.append(
            MulticraftServerSwitch(coordinator, api, server_id, server_name, entry.entry_id)
        )

    async_add_entities(entities)


class MulticraftServerSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Multicraft server switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        api,
        server_id: str,
        server_name: str,
        entry_id: str,
    ):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.api = api
        self._server_id = server_id
        self._server_name = server_name
        self._entry_id = entry_id

        # Slugify server name for entity_id
        server_slug = slugify(server_name)

        # Unique ID
        self._attr_unique_id = f"multicraft_{server_id}_switch"

        # Entity ID will be: switch.multicraft_{server_name}
        self.entity_id = f"switch.multicraft_{server_slug}"

        # Display name (shown in the device)
        self._attr_name = "Serveur"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        version = None
        if self.coordinator.data:
            server_data = self.coordinator.data.get(self._server_id, {})
            version = server_data.get("version")

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_{self._server_id}")},
            name=self._server_name,
            manufacturer="Multicraft",
            model="Minecraft Server",
            sw_version=version,
        )

    @property
    def is_on(self) -> bool:
        """Return True if the server is running."""
        if not self.coordinator.data:
            return False
        server_data = self.coordinator.data.get(self._server_id, {})
        status = server_data.get("status", "offline")
        return status == "online"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the server on."""
        try:
            result = await self.api.start_server(int(self._server_id))
            if result.get("success"):
                _LOGGER.info("Server %s (%s) started successfully", self._server_name, self._server_id)
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to start server %s: %s", self._server_name, result.get("errors"))
        except Exception as err:
            _LOGGER.error("Error starting server %s: %s", self._server_name, err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the server off."""
        try:
            result = await self.api.stop_server(int(self._server_id))
            if result.get("success"):
                _LOGGER.info("Server %s (%s) stopped successfully", self._server_name, self._server_id)
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to stop server %s: %s", self._server_name, result.get("errors"))
        except Exception as err:
            _LOGGER.error("Error stopping server %s: %s", self._server_name, err)
            raise

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:minecraft"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        server_data = self.coordinator.data.get(self._server_id, {}) if self.coordinator.data else {}
        return {
            "server_id": self._server_id,
            "server_name": self._server_name,
            "online_players": server_data.get("onlinePlayers", 0),
            "max_players": server_data.get("maxPlayers", 0),
        }
