"""Button platform for Multicraft integration."""

import logging
import re
from typing import Any

from homeassistant.components.button import ButtonEntity
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
    """Set up the Multicraft button platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    server_ids = hass.data[DOMAIN][entry.entry_id]["server_ids"]
    servers_info = hass.data[DOMAIN][entry.entry_id]["servers_info"]

    entities = []
    for server_id in server_ids:
        server_name = servers_info.get(server_id, f"Server {server_id}")
        entities.append(
            MulticraftBackupButton(coordinator, api, server_id, server_name, entry.entry_id, hass)
        )

    async_add_entities(entities)


class MulticraftBackupButton(CoordinatorEntity, ButtonEntity):
    """Representation of a Multicraft backup button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        api,
        server_id: str,
        server_name: str,
        entry_id: str,
        hass: HomeAssistant,
    ):
        """Initialize the button."""
        super().__init__(coordinator)
        self.api = api
        self._server_id = server_id
        self._server_name = server_name
        self._entry_id = entry_id
        self._hass = hass

        server_slug = slugify(server_name)

        self._attr_unique_id = f"multicraft_{server_id}_backup"
        self.entity_id = f"button.multicraft_{server_slug}_backup"
        self._attr_name = "Backup"
        self._attr_icon = "mdi:backup-restore"

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

    async def async_press(self) -> None:
        """Handle the button press - start a backup."""
        try:
            result = await self.api.start_server_backup(int(self._server_id))
            if result.get("success"):
                _LOGGER.info("Backup started for server %s (%s)", self._server_name, self._server_id)
                # Add to active backup tracking
                backup_active = self._hass.data[DOMAIN][self._entry_id].get("backup_active", set())
                backup_active.add(self._server_id)
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to start backup for server %s: %s", self._server_name, result.get("errors"))
        except Exception as err:
            _LOGGER.error("Error starting backup for server %s: %s", self._server_name, err)
            raise
