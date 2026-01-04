"""Config flow for Multicraft integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import MulticraftAPI
from .const import DOMAIN, CONF_API_URL, CONF_USERNAME, CONF_API_KEY, CONF_SERVER_IDS, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

CONF_SCAN_INTERVAL = "scan_interval"

# Step 1: Connection info
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Multicraft."""

    VERSION = 2

    def __init__(self):
        """Initialize the config flow."""
        self._api_url: str | None = None
        self._username: str | None = None
        self._api_key: str | None = None
        self._servers: list[dict[str, Any]] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return MulticraftOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - connection info."""
        errors = {}

        if user_input is not None:
            self._api_url = user_input[CONF_API_URL]
            self._username = user_input[CONF_USERNAME]
            self._api_key = user_input[CONF_API_KEY]

            # Test connection and get server list
            session = async_get_clientsession(self.hass)
            api = MulticraftAPI(
                self._api_url,
                self._username,
                self._api_key,
                session,
            )

            try:
                _LOGGER.info("Testing connection to Multicraft API at %s", api.api_url)
                self._servers = await api.get_all_servers_info()

                if not self._servers:
                    errors["base"] = "no_servers"
                    _LOGGER.error("No servers found for user %s", self._username)
                else:
                    _LOGGER.info("Found %d servers", len(self._servers))
                    return await self.async_step_servers()

            except Exception as err:
                error_msg = str(err)
                _LOGGER.exception("Error connecting to Multicraft API: %s", err)
                if "Connection" in error_msg or "connecter" in error_msg.lower():
                    errors["base"] = "cannot_connect"
                elif "API Error" in error_msg:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_servers(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle server selection step."""
        errors = {}

        if user_input is not None:
            selected_ids = user_input.get(CONF_SERVER_IDS, [])

            if not selected_ids:
                errors["base"] = "no_server_selected"
            else:
                selected_names = []
                for server in self._servers:
                    if str(server["id"]) in selected_ids:
                        selected_names.append(server["name"])

                title = f"Multicraft ({', '.join(selected_names[:2])}{'...' if len(selected_names) > 2 else ''})"

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_API_URL: self._api_url,
                        CONF_USERNAME: self._username,
                        CONF_API_KEY: self._api_key,
                        CONF_SERVER_IDS: selected_ids,
                    },
                )

        server_options = [
            {
                "value": str(server["id"]),
                "label": f"{server['name']} (ID: {server['id']}) - {server['status']}",
            }
            for server in self._servers
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_SERVER_IDS): SelectSelector(
                    SelectSelectorConfig(
                        options=server_options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="servers",
            data_schema=schema,
            errors=errors,
        )


class MulticraftOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Multicraft options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._servers: list[dict[str, Any]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}

        current_server_ids = self.config_entry.data.get(CONF_SERVER_IDS, [])
        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        session = async_get_clientsession(self.hass)
        api = MulticraftAPI(
            self.config_entry.data[CONF_API_URL],
            self.config_entry.data[CONF_USERNAME],
            self.config_entry.data[CONF_API_KEY],
            session,
        )

        # Try to get servers from cache first (from coordinator)
        cached_servers = None
        if DOMAIN in self.hass.data and self.config_entry.entry_id in self.hass.data[DOMAIN]:
            entry_data = self.hass.data[DOMAIN][self.config_entry.entry_id]
            servers_info = entry_data.get("servers_info", {})
            if servers_info:
                cached_servers = [
                    {"id": int(sid), "name": name, "status": "cached"}
                    for sid, name in servers_info.items()
                ]
        try:
            self._servers = await api.get_all_servers_info()
        except Exception as err:
            _LOGGER.warning("Error fetching servers from API: %s, using cached data", err)
            if cached_servers:
                self._servers = cached_servers
            else:
                self._servers = [
                    {"id": int(sid), "name": f"Server {sid}", "status": "unknown"}
                    for sid in current_server_ids
                ]
                if not self._servers:
                    errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            selected_ids = user_input.get(CONF_SERVER_IDS, [])
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

            if not selected_ids:
                errors["base"] = "no_server_selected"
            else:
                new_data = {**self.config_entry.data, CONF_SERVER_IDS: selected_ids}
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )

                return self.async_create_entry(
                    title="",
                    data={CONF_SCAN_INTERVAL: scan_interval},
                )

        server_options = [
            {
                "value": str(server["id"]),
                "label": f"{server['name']} (ID: {server['id']}) - {server['status']}",
            }
            for server in self._servers
        ]

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SERVER_IDS, default=current_server_ids
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=server_options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=current_scan_interval
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=10,
                        max=300,
                        step=5,
                        mode=NumberSelectorMode.SLIDER,
                        unit_of_measurement="secondes",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

    def __init__(self, message: str = "Impossible de se connecter."):
        """Initialize the error with a custom message."""
        super().__init__(message)
        self.message = message
