"""Multicraft integration for Home Assistant."""

import asyncio
import logging
import socket
import struct
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta

from .api import MulticraftAPI
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, CONF_SERVER_IDS, CONF_SERVER_ID

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "sensor"]

CONF_SCAN_INTERVAL = "scan_interval"


async def async_ping_minecraft_server(host: str, port: int, timeout: float = 5.0) -> dict[str, Any]:
    """Ping a Minecraft server to get version and latency."""
    try:
        start_time = time.time()

        # Create socket connection
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )

        # Build handshake packet
        protocol_version = 47  # Minecraft 1.8+
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

        # Send status request
        writer.write(b'\x01\x00')
        await writer.drain()

        # Read response
        _read_varint(reader)  # Packet length
        await asyncio.wait_for(reader.read(1), timeout=timeout)  # Packet ID

        # Read JSON string length
        json_length = await _async_read_varint(reader, timeout)

        # Read JSON data
        json_data = await asyncio.wait_for(reader.read(json_length), timeout=timeout)

        writer.close()
        await writer.wait_closed()

        latency = int((time.time() - start_time) * 1000)

        # Parse JSON response
        import json
        try:
            response = json.loads(json_data.decode('utf-8'))
            version = response.get('version', {}).get('name', 'Unknown')
            return {
                'latency': latency,
                'version': version,
                'online': True,
            }
        except json.JSONDecodeError:
            return {
                'latency': latency,
                'version': 'Unknown',
                'online': True,
            }

    except Exception as err:
        _LOGGER.debug("Could not ping Minecraft server %s:%s: %s", host, port, err)
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

        # Get connection info (IP/port) for each selected server
        for server_id in server_ids:
            try:
                server_details = await api.get_server(int(server_id))
                if server_details.get("success"):
                    server_data = server_details.get("data", {}).get("Server", {})
                    ip = server_data.get("ip", "")
                    port = server_data.get("port", 25565)
                    if ip:
                        servers_connection[server_id] = {"ip": ip, "port": int(port)}
            except Exception as err:
                _LOGGER.warning("Could not get connection info for server %s: %s", server_id, err)

    except Exception as err:
        _LOGGER.warning("Could not fetch server info: %s", err)

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
                    ping_result = await async_ping_minecraft_server(conn["ip"], conn["port"])
                    server_data["latency"] = ping_result.get("latency")
                    server_data["version"] = ping_result.get("version")
                else:
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
