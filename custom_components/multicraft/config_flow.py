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
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import MulticraftAPI
from .const import (
    DOMAIN, CONF_API_URL, CONF_USERNAME, CONF_API_KEY, CONF_SERVER_IDS,
    DEFAULT_SCAN_INTERVAL, CONF_FTP_PASSWORD,
    CONF_DEFAULT_DESTINATION, CONF_BACKUP_ROTATION, CONF_BACKUP_RETENTION_DAYS,
    CONF_KEEP_BACKUP_ON_SERVER, DEFAULT_BACKUP_ROTATION, DEFAULT_BACKUP_RETENTION_DAYS,
    DEFAULT_KEEP_BACKUP_ON_SERVER,
)

_LOGGER = logging.getLogger(__name__)

CONF_SCAN_INTERVAL = "scan_interval"

# Step 1: Connection info
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_FTP_PASSWORD, default=""): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Multicraft."""

    VERSION = 3

    def __init__(self):
        """Initialize the config flow."""
        self._api_url: str | None = None
        self._username: str | None = None
        self._api_key: str | None = None
        self._ftp_password: str = ""
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
            self._ftp_password = user_input.get(CONF_FTP_PASSWORD, "")

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
                        CONF_FTP_PASSWORD: self._ftp_password,
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
        # Note: self.config_entry is automatically set by the parent class
        self._servers: list[dict[str, Any]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}
        fallback_servers = []

        # Get current values with safe defaults
        current_server_ids = self.config_entry.data.get(CONF_SERVER_IDS, [])
        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        current_ftp_password = self.config_entry.data.get(CONF_FTP_PASSWORD, "")
        current_default_destination = self.config_entry.options.get(
            CONF_DEFAULT_DESTINATION, ""
        )
        current_backup_rotation = self.config_entry.options.get(
            CONF_BACKUP_ROTATION, DEFAULT_BACKUP_ROTATION
        )
        current_retention_days = self.config_entry.options.get(
            CONF_BACKUP_RETENTION_DAYS, DEFAULT_BACKUP_RETENTION_DAYS
        )
        current_keep_on_server = self.config_entry.options.get(
            CONF_KEEP_BACKUP_ON_SERVER, DEFAULT_KEEP_BACKUP_ON_SERVER
        )

        try:

            _LOGGER.debug("Options flow init: server_ids=%s, scan_interval=%s",
                         current_server_ids, current_scan_interval)

            # Build fallback list from current config (always available)
            for sid in current_server_ids:
                try:
                    fallback_servers.append({
                        "id": int(sid),
                        "name": f"Server {sid}",
                        "status": "unknown"
                    })
                except (ValueError, TypeError) as e:
                    _LOGGER.warning("Invalid server ID %s: %s", sid, e)

            # Try to get servers from cache first (from coordinator) - this avoids API calls
            cached_servers = []
            if DOMAIN in self.hass.data and self.config_entry.entry_id in self.hass.data[DOMAIN]:
                entry_data = self.hass.data[DOMAIN][self.config_entry.entry_id]
                servers_info = entry_data.get("servers_info", {})
                _LOGGER.debug("Found cached servers_info: %s", servers_info)
                if servers_info:
                    for sid, name in servers_info.items():
                        try:
                            cached_servers.append({
                                "id": int(sid),
                                "name": name,
                                "status": "en cache"
                            })
                        except (ValueError, TypeError) as e:
                            _LOGGER.warning("Invalid cached server ID %s: %s", sid, e)

            # Use cached servers if available (preferred - no API call needed)
            if cached_servers:
                self._servers = cached_servers
                _LOGGER.debug("Using cached server list for options flow: %s", cached_servers)
            elif fallback_servers:
                # Use fallback without calling API
                self._servers = fallback_servers
                _LOGGER.debug("Using fallback server list for options flow: %s", fallback_servers)
            else:
                # No servers at all - show empty form
                self._servers = []
                _LOGGER.warning("No servers available for options flow")

        except Exception as err:
            _LOGGER.exception("Error in options flow setup: %s", err)
            self._servers = fallback_servers if fallback_servers else []
            if not self._servers:
                errors["base"] = "cannot_connect"

        # Ensure we always have at least the currently configured servers
        if not self._servers and fallback_servers:
            self._servers = fallback_servers

        if user_input is not None and not errors:
            selected_ids = user_input.get(CONF_SERVER_IDS)
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

            # If server selection is not in form (API was unreachable), keep current selection
            if selected_ids is None:
                selected_ids = current_server_ids

            if not selected_ids:
                errors["base"] = "no_server_selected"
            else:
                ftp_password = user_input.get(CONF_FTP_PASSWORD, current_ftp_password)
                new_data = {
                    **self.config_entry.data,
                    CONF_SERVER_IDS: selected_ids,
                    CONF_FTP_PASSWORD: ftp_password,
                }
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )

                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SCAN_INTERVAL: scan_interval,
                        CONF_DEFAULT_DESTINATION: user_input.get(
                            CONF_DEFAULT_DESTINATION, current_default_destination
                        ),
                        CONF_BACKUP_ROTATION: user_input.get(
                            CONF_BACKUP_ROTATION, current_backup_rotation
                        ),
                        CONF_BACKUP_RETENTION_DAYS: int(user_input.get(
                            CONF_BACKUP_RETENTION_DAYS, current_retention_days
                        )),
                        CONF_KEEP_BACKUP_ON_SERVER: user_input.get(
                            CONF_KEEP_BACKUP_ON_SERVER, current_keep_on_server
                        ),
                    },
                )

        server_options = [
            {
                "value": str(server["id"]),
                "label": f"{server['name']} (ID: {server['id']}) - {server['status']}",
            }
            for server in self._servers
        ]

        # Build common fields for both schema variants
        ftp_password_field = {
            vol.Optional(
                CONF_FTP_PASSWORD, default=current_ftp_password
            ): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.PASSWORD,
                )
            ),
        }

        backup_fields = {
            vol.Optional(
                CONF_DEFAULT_DESTINATION, default=current_default_destination
            ): TextSelector(TextSelectorConfig()),
            vol.Optional(
                CONF_BACKUP_ROTATION, default=current_backup_rotation
            ): BooleanSelector(),
            vol.Optional(
                CONF_BACKUP_RETENTION_DAYS, default=current_retention_days
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=365,
                    step=1,
                    mode=NumberSelectorMode.SLIDER,
                    unit_of_measurement="jours",
                )
            ),
            vol.Optional(
                CONF_KEEP_BACKUP_ON_SERVER, default=current_keep_on_server
            ): BooleanSelector(),
        }

        if server_options:
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
                    **ftp_password_field,
                    **backup_fields,
                }
            )
        else:
            # No servers available - only show scan interval option
            schema = vol.Schema(
                {
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
                    **ftp_password_field,
                    **backup_fields,
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
