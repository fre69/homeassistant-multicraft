"""Multicraft API Client."""

import hashlib
import hmac
import json
import logging
from typing import Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession
import aiohttp

_LOGGER = logging.getLogger(__name__)


class MulticraftAPI:
    """Multicraft API client."""

    def __init__(
        self,
        api_url: str,
        username: str,
        api_key: str,
        session: aiohttp.ClientSession,
    ):
        """Initialize the Multicraft API client."""
        # Nettoyer l'URL et s'assurer qu'elle se termine par /api.php
        self.api_url = api_url.rstrip("/")
        
        # Si l'URL ne se termine pas déjà par /api.php, l'ajouter
        if not self.api_url.endswith("/api.php"):
            # Si l'URL se termine par /multicraft, ajouter /api.php
            if self.api_url.endswith("/multicraft"):
                self.api_url = f"{self.api_url}/api.php"
            # Si l'utilisateur a fourni juste l'IP ou l'URL de base, ajouter /multicraft/api.php
            elif not "/multicraft" in self.api_url:
                # Vérifier si c'est juste une IP ou un domaine
                parts = self.api_url.split("://", 1)
                if len(parts) == 2:
                    # Il y a un protocole (http:// ou https://)
                    domain_path = parts[1]
                    if "/" not in domain_path:
                        # Juste le domaine/IP, ajouter /multicraft/api.php
                        self.api_url = f"{self.api_url}/multicraft/api.php"
                    else:
                        # Il y a déjà un chemin, ajouter /api.php
                        self.api_url = f"{self.api_url}/api.php"
                else:
                    # Pas de protocole, ajouter http:// et /multicraft/api.php
                    self.api_url = f"http://{self.api_url}/multicraft/api.php"
            else:
                # Il y a déjà /multicraft quelque part mais pas à la fin, ajouter /api.php
                self.api_url = f"{self.api_url}/api.php"
        
        self.username = username
        self.api_key = api_key
        self.session = session
        _LOGGER.debug("Multicraft API URL: %s", self.api_url)

    def _compute_signature(self, params: dict[str, Any]) -> str:
        """Compute HMAC-SHA256 signature for API request.

        Multicraft API requires signing the request parameters with HMAC-SHA256.
        The signature is computed by concatenating all parameter keys and values
        (sorted alphabetically by key) and signing with the API key.
        """
        # Build the string to sign: concatenate key+value for all params
        # Parameters must be sorted alphabetically by key
        string_to_sign = ""
        for key in sorted(params.keys()):
            string_to_sign += str(key) + str(params[key])

        # Compute HMAC-SHA256
        signature = hmac.new(
            self.api_key.strip().encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return signature

    async def _call_api(self, method: str, **params) -> dict[str, Any]:
        """Make an API call to Multicraft."""
        url = self.api_url

        # Build the base parameters (without the API key signature)
        base_params = {
            "_MulticraftAPIMethod": method,
            "_MulticraftAPIUser": self.username,
            **params,
        }

        # Compute HMAC-SHA256 signature
        signature = self._compute_signature(base_params)

        # Add the signature as the API key
        data = {
            **base_params,
            "_MulticraftAPIKey": signature,
        }

        _LOGGER.debug("Calling Multicraft API: %s with method: %s", url, method)
        _LOGGER.debug("API User: %s, Signature: %s...", self.username, signature[:16])
        
        try:
            async with self.session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                status = response.status
                _LOGGER.debug("Response status: %s", status)
                
                # Si le statut n'est pas 200, lire le texte pour voir l'erreur
                if status != 200:
                    text = await response.text()
                    _LOGGER.error("HTTP Error %s: %s", status, text[:200])
                    raise Exception(f"HTTP Error {status}: {text[:200]}")
                
                # Multicraft API retourne du JSON
                # On lit d'abord le texte, puis on parse le JSON
                text = await response.text()
                _LOGGER.debug("API Raw Response: %s", text[:500])

                try:
                    result = json.loads(text)
                    _LOGGER.debug("API Response parsed: %s", result)
                except Exception as json_err:
                    _LOGGER.error("Response is not JSON. Status: %s, Content: %s", status, text[:500])
                    raise Exception(f"Invalid response format from Multicraft API (not JSON). Status: {status}, Response: {text[:200]}") from json_err
                
                if not result.get("success", False):
                    error_msg = result.get("errors", ["Unknown error"])
                    _LOGGER.error("Multicraft API error: %s", error_msg)
                    raise Exception(f"API Error: {error_msg}")
                return result
        except aiohttp.ClientConnectorError as err:
            _LOGGER.error("Connection error to Multicraft API at %s: %s", url, err)
            raise Exception(f"Impossible de se connecter à {url}. Vérifiez que l'URL est correcte et que le serveur est accessible.") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Error calling Multicraft API at %s: %s", url, err)
            raise Exception(f"Erreur de connexion: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error: %s", err)
            raise

    async def get_server_status(self, server_id: int, players: bool = False) -> dict[str, Any]:
        """Get server status."""
        return await self._call_api("getServerStatus", id=server_id, players=1 if players else 0)

    async def start_server(self, server_id: int) -> dict[str, Any]:
        """Start a server."""
        return await self._call_api("startServer", id=server_id)

    async def stop_server(self, server_id: int) -> dict[str, Any]:
        """Stop a server."""
        return await self._call_api("stopServer", id=server_id)

    async def restart_server(self, server_id: int) -> dict[str, Any]:
        """Restart a server."""
        return await self._call_api("restartServer", id=server_id)

    async def get_server(self, server_id: int) -> dict[str, Any]:
        """Get server information."""
        return await self._call_api("getServer", id=server_id)

    async def list_servers(self) -> dict[str, Any]:
        """List all servers the user has access to."""
        return await self._call_api("listServers")

    async def get_server_by_name(self, name: str) -> dict[str, Any]:
        """Find a server by name."""
        return await self._call_api("findServers", name=name)

    async def get_all_servers_info(self) -> list[dict[str, Any]]:
        """Get information for all servers the user has access to.

        Returns a list of server info dicts with id, name, and status.
        """
        servers = []
        result = await self.list_servers()

        if result.get("success") and result.get("data", {}).get("Servers"):
            server_ids = result["data"]["Servers"]
            # server_ids is a dict like {"1": "ServerName1", "4": "ServerName4"}
            for server_id, server_name in server_ids.items():
                try:
                    # Get server status
                    status_result = await self.get_server_status(int(server_id))
                    status_data = status_result.get("data", {})

                    servers.append({
                        "id": int(server_id),
                        "name": server_name,
                        "status": status_data.get("status", "unknown"),
                        "online_players": status_data.get("onlinePlayers", "0"),
                        "max_players": status_data.get("maxPlayers", "0"),
                    })
                except Exception as err:
                    _LOGGER.warning("Could not get status for server %s: %s", server_id, err)
                    servers.append({
                        "id": int(server_id),
                        "name": server_name,
                        "status": "unknown",
                        "online_players": "0",
                        "max_players": "0",
                    })

        return servers

