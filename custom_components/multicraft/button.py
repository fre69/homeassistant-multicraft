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

from .const import (
    DOMAIN, CONF_FTP_PASSWORD, CONF_DEFAULT_DESTINATION, CONF_BACKUP_ROTATION,
    CONF_BACKUP_RETENTION_DAYS, CONF_KEEP_BACKUP_ON_SERVER,
    DEFAULT_BACKUP_ROTATION, DEFAULT_BACKUP_RETENTION_DAYS, DEFAULT_KEEP_BACKUP_ON_SERVER,
)
from . import async_backup_and_download

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
        """Handle the button press - start a backup.

        Uses the same async_backup_and_download code path as the download_backup service.
        Runs in background since backup+download can take several minutes.
        """
        # Get config entry for options and FTP password
        config_entry = None
        for ce in self._hass.config_entries.async_entries(DOMAIN):
            if ce.entry_id == self._entry_id:
                config_entry = ce
                break

        ftp_password = config_entry.data.get(CONF_FTP_PASSWORD, "") if config_entry else ""
        options = config_entry.options if config_entry else {}

        rotation_enabled = options.get(CONF_BACKUP_ROTATION, DEFAULT_BACKUP_ROTATION)
        retention_days = int(options.get(CONF_BACKUP_RETENTION_DAYS, DEFAULT_BACKUP_RETENTION_DAYS))
        keep_on_server = options.get(CONF_KEEP_BACKUP_ON_SERVER, DEFAULT_KEEP_BACKUP_ON_SERVER)
        destination = options.get(CONF_DEFAULT_DESTINATION, "") or "/media/multicraft_backups/"

        backup_active = self._hass.data[DOMAIN][self._entry_id].get("backup_active", set())

        async def _background_backup():
            try:
                await async_backup_and_download(
                    self._hass, self.api, self._server_id, ftp_password,
                    destination, rotation_enabled, retention_days,
                    keep_on_server, backup_active, self.coordinator,
                )
            except Exception as err:
                _LOGGER.error(
                    "Background backup failed for server %s: %s",
                    self._server_name, err,
                )

        self._hass.async_create_task(_background_backup())
        _LOGGER.info(
            "Backup started in background for server %s (%s)",
            self._server_name, self._server_id,
        )
