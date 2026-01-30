"""Multicraft integration for Home Assistant."""

import asyncio
import logging
import socket
import struct
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta

from urllib.parse import urlparse

from .api import MulticraftAPI
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, CONF_SERVER_IDS, CONF_SERVER_ID

_LOGGER = logging.getLogger(__name__)


def _is_valid_ip(ip: str) -> bool:
    """Check if IP is valid and routable (not 0.0.0.0 or empty)."""
    if not ip:
        return False
    # 0.0.0.0 means "listen on all interfaces" - not routable
    if ip == "0.0.0.0":
        return False
    return True


def _extract_host_from_url(url: str) -> str:
    """Extract host/IP from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        return ""

PLATFORMS = ["switch", "sensor"]

CONF_SCAN_INTERVAL = "scan_interval"


async def async_ping_minecraft_server(host: str, port: int, timeout: float = 5.0) -> dict[str, Any]:
    """Ping a Minecraft server to get version and latency using the Minecraft protocol."""
    import json

    try:
        start_time = time.time()

        # Create socket connection
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )

        # Build handshake packet
        protocol_version = 767  # Minecraft 1.21+ (use modern protocol)
        host_bytes = host.encode('utf-8')

        # Handshake data
        handshake_data = (
            b'\x00' +  # Packet ID (handshake)
            _encode_varint(protocol_version) +
            _encode_varint(len(host_bytes)) + host_bytes +
            struct.pack('>H', port) +
            b'\x01'  # Next state (status)
        )

        # Send handshake packet
        writer.write(_encode_varint(len(handshake_data)) + handshake_data)

        # Send status request (packet ID 0x00, no data)
        writer.write(b'\x01\x00')
        await writer.drain()

        # Read response packet
        # First: read packet length (VarInt)
        packet_length = await _async_read_varint(reader, timeout)
        _LOGGER.debug("Received packet length: %s", packet_length)

        # Read packet ID (VarInt, should be 0x00 for status response)
        packet_id = await _async_read_varint(reader, timeout)
        _LOGGER.debug("Received packet ID: %s", packet_id)

        if packet_id != 0:
            _LOGGER.warning("Unexpected packet ID: %s (expected 0)", packet_id)

        # Read JSON string length (VarInt)
        json_length = await _async_read_varint(reader, timeout)
        _LOGGER.debug("JSON length: %s", json_length)

        # Sanity check on json_length
        if json_length <= 0 or json_length > 100000:
            _LOGGER.warning("Invalid JSON length: %s", json_length)
            writer.close()
            await writer.wait_closed()
            return {'latency': None, 'version': None, 'online': False}

        # Read JSON data
        json_data = b''
        while len(json_data) < json_length:
            chunk = await asyncio.wait_for(
                reader.read(json_length - len(json_data)),
                timeout=timeout
            )
            if not chunk:
                break
            json_data += chunk

        writer.close()
        await writer.wait_closed()

        latency = int((time.time() - start_time) * 1000)

        # Parse JSON response
        try:
            response = json.loads(json_data.decode('utf-8'))
            version = response.get('version', {}).get('name', 'Unknown')
            _LOGGER.debug("Minecraft server response: version=%s", version)
            return {
                'latency': latency,
                'version': version,
                'online': True,
            }
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            _LOGGER.debug("Could not parse server response: %s, raw data: %s", err, json_data[:100])
            return {
                'latency': latency,
                'version': 'Unknown',
                'online': True,
            }

    except Exception as err:
        _LOGGER.warning("Could not ping Minecraft server %s:%s: %s", host, port, err)
        return {
            'latency': None,
            'version': None,
            'online': False,
        }


def _encode_varint(value: int) -> bytes:
    """Encode an integer as a Minecraft VarInt."""
    result = b''
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            result += bytes([byte | 0x80])
        else:
            result += bytes([byte])
            break
    return result


def _read_varint(reader) -> int:
    """Read a VarInt synchronously (not used in async context)."""
    return 0


async def _async_read_varint(reader, timeout: float) -> int:
    """Read a VarInt from async reader."""
    result = 0
    shift = 0
    while True:
        byte_data = await asyncio.wait_for(reader.read(1), timeout=timeout)
        if not byte_data:
            raise ConnectionError("Connection closed")
        byte = byte_data[0]
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return result


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Multicraft from a config entry."""
    api_url = entry.data["api_url"]
    username = entry.data["username"]
    api_key = entry.data["api_key"]

    # Support both old (single server) and new (multiple servers) config
    server_ids = entry.data.get(CONF_SERVER_IDS, [])
    if not server_ids and CONF_SERVER_ID in entry.data:
        server_ids = [str(entry.data[CONF_SERVER_ID])]

    # Get scan interval from options
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    session = async_get_clientsession(hass)
    api = MulticraftAPI(api_url, username, api_key, session)

    # Get server names and connection info
    servers_info = {}
    servers_connection = {}
    try:
        all_servers = await api.get_all_servers_info()
        for server in all_servers:
            server_id = str(server["id"])
            servers_info[server_id] = server["name"]

        # Extract fallback IP from API URL (useful when server reports 0.0.0.0)
        fallback_ip = _extract_host_from_url(api_url)
        _LOGGER.debug("Fallback IP from API URL: %s", fallback_ip)

        # Get connection info (IP/port) for each selected server
        for server_id in server_ids:
            try:
                server_details = await api.get_server(int(server_id))
                _LOGGER.debug("Server %s details: %s", server_id, server_details)
                if server_details.get("success"):
                    server_data = server_details.get("data", {}).get("Server", {})
                    _LOGGER.debug("Server %s data keys: %s", server_id, list(server_data.keys()))

                    # Try multiple possible field names for IP
                    raw_ip = (
                        server_data.get("ip") or
                        server_data.get("daemon_ip") or
                        server_data.get("daemonIp") or
                        server_data.get("server_ip") or
                        server_data.get("serverIp") or
                        ""
                    )

                    # Use fallback IP if the server reports 0.0.0.0 or empty
                    if _is_valid_ip(raw_ip):
                        ip = raw_ip
                    elif fallback_ip:
                        _LOGGER.info(
                            "Server %s reports IP '%s', using API host '%s' instead",
                            server_id, raw_ip, fallback_ip
                        )
                        ip = fallback_ip
                    else:
                        ip = ""

                    # Try multiple possible field names for port
                    port = (
                        server_data.get("port") or
                        server_data.get("server_port") or
                        server_data.get("serverPort") or
                        25565
                    )

                    _LOGGER.debug("Server %s - IP: %s, Port: %s", server_id, ip, port)

                    if ip:
                        servers_connection[server_id] = {"ip": ip, "port": int(port)}
                    else:
                        _LOGGER.warning("No IP found for server %s. Available fields: %s", server_id, server_data)
            except Exception as err:
                _LOGGER.warning("Could not get connection info for server %s: %s", server_id, err)

    except Exception as err:
        raise ConfigEntryNotReady(f"Could not connect to Multicraft API: {err}") from err

    async def async_update_data():
        """Fetch data from Multicraft API for all servers."""
        data = {}
        for server_id in server_ids:
            try:
                status = await api.get_server_status(int(server_id), players=True)
                server_data = status.get("data", {})
                server_data["server_name"] = servers_info.get(server_id, f"Server {server_id}")

                # If server is online and we have connection info, ping for latency/version
                if server_data.get("status") == "online" and server_id in servers_connection:
                    conn = servers_connection[server_id]
                    _LOGGER.debug("Pinging Minecraft server %s at %s:%s", server_id, conn["ip"], conn["port"])
                    ping_result = await async_ping_minecraft_server(conn["ip"], conn["port"])
                    _LOGGER.debug("Ping result for server %s: %s", server_id, ping_result)
                    server_data["latency"] = ping_result.get("latency")
                    server_data["version"] = ping_result.get("version")
                else:
                    _LOGGER.debug(
                        "Skipping ping for server %s: status=%s, has_connection=%s",
                        server_id, server_data.get("status"), server_id in servers_connection
                    )
                    server_data["latency"] = None
                    server_data["version"] = None

                data[server_id] = server_data
            except Exception as err:
                _LOGGER.error("Error fetching data for server %s: %s", server_id, err)
                data[server_id] = {
                    "status": "unknown",
                    "server_name": servers_info.get(server_id, f"Server {server_id}"),
                    "error": str(err),
                    "latency": None,
                    "version": None,
                }
        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "server_ids": server_ids,
        "servers_info": servers_info,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
