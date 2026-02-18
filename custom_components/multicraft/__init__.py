"""Multicraft integration for Home Assistant."""

import asyncio
import logging
import socket
import struct
import time
from typing import Any

import ftplib
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MulticraftAPI
from .const import (
    DOMAIN, DEFAULT_SCAN_INTERVAL, CONF_SERVER_IDS, CONF_SERVER_ID, CONF_FTP_PASSWORD,
    CONF_DEFAULT_DESTINATION, CONF_BACKUP_ROTATION, CONF_BACKUP_RETENTION_DAYS,
    CONF_KEEP_BACKUP_ON_SERVER, DEFAULT_BACKUP_ROTATION, DEFAULT_BACKUP_RETENTION_DAYS,
    DEFAULT_KEEP_BACKUP_ON_SERVER,
)

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

PLATFORMS = ["switch", "sensor", "button"]

CONF_SCAN_INTERVAL = "scan_interval"


def _ftp_rename(ftp_host: str, ftp_port: int, ftp_user: str,
                ftp_password: str, remote_path: str, new_path: str) -> None:
    """Rename a file on FTP server (runs in executor thread)."""
    ftp = ftplib.FTP()
    ftp.connect(ftp_host, ftp_port, timeout=30)
    ftp.login(ftp_user, ftp_password)
    try:
        ftp.rename(remote_path, new_path)
        _LOGGER.info("Renamed FTP file: %s -> %s", remote_path, new_path)
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()


def _cleanup_old_backups_local(directory: str, retention_days: int) -> int:
    """Delete .zip backup files older than retention_days in local directory (runs in executor)."""
    if not os.path.isdir(directory):
        return 0
    cutoff = time.time() - (retention_days * 86400)
    deleted = 0
    for filename in os.listdir(directory):
        if not filename.endswith(".zip"):
            continue
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath) and os.path.getmtime(filepath) < cutoff:
            os.remove(filepath)
            _LOGGER.info("Retention: deleted local backup %s", filepath)
            deleted += 1
    return deleted


def _cleanup_old_backups_ftp(ftp_host: str, ftp_port: int, ftp_user: str,
                             ftp_password: str, remote_dir: str,
                             retention_days: int) -> int:
    """Delete .zip backup files older than retention_days on FTP server (runs in executor)."""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    ftp = ftplib.FTP()
    ftp.connect(ftp_host, ftp_port, timeout=30)
    ftp.login(ftp_user, ftp_password)
    deleted = 0

    try:
        if remote_dir:
            ftp.cwd(remote_dir)
        files = ftp.nlst()
        for filename in files:
            if not filename.endswith(".zip"):
                continue
            try:
                mdtm_response = ftp.sendcmd(f"MDTM {filename}")
                timestamp_str = mdtm_response.split()[1]
                file_dt = datetime.strptime(timestamp_str[:14], "%Y%m%d%H%M%S")
                if file_dt < cutoff:
                    ftp.delete(filename)
                    _LOGGER.info("Retention: deleted FTP backup %s/%s", remote_dir, filename)
                    deleted += 1
            except Exception as err:
                _LOGGER.debug("Could not check/delete FTP file %s: %s", filename, err)
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()

    return deleted


async def async_cleanup_old_backups(
    hass: HomeAssistant,
    ftp_host: str, ftp_port: int, ftp_user: str, ftp_password: str,
    remote_dir: str, local_dir: str, retention_days: int,
) -> None:
    """Clean up old backups on both local storage and FTP server. Best effort."""
    if retention_days <= 0:
        return

    try:
        await hass.async_add_executor_job(
            _cleanup_old_backups_local, local_dir, retention_days
        )
    except Exception as err:
        _LOGGER.warning("Local backup cleanup failed: %s", err)

    try:
        await hass.async_add_executor_job(
            _cleanup_old_backups_ftp, ftp_host, ftp_port, ftp_user,
            ftp_password, remote_dir, retention_days
        )
    except Exception as err:
        _LOGGER.warning("FTP backup cleanup failed: %s", err)


async def async_backup_and_download(
    hass: HomeAssistant,
    api: "MulticraftAPI",
    server_id: str,
    ftp_password: str,
    destination_path: str,
    rotation_enabled: bool,
    retention_days: int,
    keep_on_server: bool,
    backup_active_set: set,
    coordinator: DataUpdateCoordinator,
) -> str | None:
    """Complete backup workflow: rotate, backup, poll, download, cleanup.

    If ftp_password is empty, only triggers a server-side backup (no download).
    Returns the local path of the downloaded backup file, or None if no download.
    Raises HomeAssistantError on failure.
    """
    sid = int(server_id)
    has_ftp = bool(ftp_password)

    # Step 1: Start backup
    try:
        await api.start_server_backup(sid)
    except Exception as err:
        raise HomeAssistantError(f"Failed to start backup: {err}") from err

    # Add to active set for coordinator polling
    backup_active_set.add(server_id)

    # Without FTP credentials, we can only trigger the backup server-side
    if not has_ftp:
        _LOGGER.info("Backup started for server %s (no FTP password, download skipped)", server_id)
        await coordinator.async_request_refresh()
        return None

    # Step 2: Poll backup status every 5s, timeout 10 minutes
    # Wait until we see "running" at least once, then wait until it finishes
    # Tolerate transient connection errors (server may be under load during backup)
    timeout = 600
    start_time = time.time()
    backup_file = None
    ftp_address = None
    seen_running = False
    consecutive_errors = 0
    max_consecutive_errors = 5

    while time.time() - start_time < timeout:
        await asyncio.sleep(5)
        try:
            result = await api.get_server_backup_status(sid)
            consecutive_errors = 0  # Reset on success
            data = result.get("data", {})
            status = data.get("status", "")

            _LOGGER.debug(
                "Backup poll for server %s: status=%s, file=%s, ftp=%s",
                server_id, status, data.get("file", ""), data.get("ftp", ""),
            )

            if status == "running":
                seen_running = True
            elif seen_running:
                # Was running, now finished
                backup_file = data.get("file", "")
                ftp_address = data.get("ftp", "")
                break
            # If not yet seen running, keep polling (backup may not have started yet)
        except Exception as err:
            consecutive_errors += 1
            _LOGGER.warning(
                "Error polling backup status for server %s (%d/%d): %s",
                server_id, consecutive_errors, max_consecutive_errors, err,
            )
            if consecutive_errors >= max_consecutive_errors:
                backup_active_set.discard(server_id)
                raise HomeAssistantError(
                    f"Backup polling failed after {max_consecutive_errors} consecutive errors: {err}"
                ) from err
            # Transient error, will retry on next iteration
    else:
        backup_active_set.discard(server_id)
        raise HomeAssistantError("Backup timed out after 10 minutes")

    # Remove from active set
    backup_active_set.discard(server_id)

    if not backup_file or not ftp_address:
        raise HomeAssistantError("Backup completed but no file/FTP information returned")

    _LOGGER.info(
        "Backup complete for server %s, downloading: file=%s, ftp=%s",
        server_id, backup_file, ftp_address,
    )

    # Step 3: Download via FTP
    ftp_parts = ftp_address.split(":")
    ftp_host = ftp_parts[0]
    ftp_port = int(ftp_parts[1]) if len(ftp_parts) > 1 else 21
    ftp_user = f"admin.{server_id}"

    remote_filename = os.path.basename(backup_file)
    remote_dir = backup_file.rsplit("/", 1)[0] if "/" in backup_file else ""

    def ftp_download():
        """Download file via FTP (runs in executor)."""
        os.makedirs(destination_path, exist_ok=True)
        local_file_path = os.path.join(destination_path, remote_filename)

        ftp = ftplib.FTP()
        ftp.connect(ftp_host, ftp_port, timeout=60)
        ftp.login(ftp_user, ftp_password)

        try:
            # Log current directory and available files for debugging
            cwd = ftp.pwd()
            _LOGGER.debug("FTP connected, cwd=%s, downloading %s", cwd, backup_file)

            with open(local_file_path, 'wb') as f:
                ftp.retrbinary(f'RETR {backup_file}', f.write)
        finally:
            ftp.quit()

        return local_file_path

    try:
        downloaded_path = await hass.async_add_executor_job(ftp_download)
    except Exception as err:
        hass.bus.async_fire("multicraft_backup_failed", {
            "server_id": server_id,
            "error": str(err),
        })
        raise HomeAssistantError(f"FTP download failed: {err}") from err

    # Step 4: Rotation — rename downloaded file and FTP file with date suffix
    if rotation_enabled:
        date_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_part, _, ext = remote_filename.rpartition(".")
        if not name_part:
            name_part = remote_filename
            ext = ""
        new_name = f"{name_part}_{date_suffix}.{ext}" if ext else f"{name_part}_{date_suffix}"

        # Rename local file
        new_local_path = os.path.join(destination_path, new_name)
        try:
            await hass.async_add_executor_job(os.rename, downloaded_path, new_local_path)
            _LOGGER.info("Rotated local backup: %s -> %s", remote_filename, new_name)
            downloaded_path = new_local_path
        except Exception as err:
            _LOGGER.warning("Failed to rename local backup: %s", err)

        # Rename on FTP (only if keeping on server)
        if keep_on_server:
            new_remote = f"{remote_dir}/{new_name}" if remote_dir else new_name
            try:
                await hass.async_add_executor_job(
                    _ftp_rename, ftp_host, ftp_port, ftp_user, ftp_password,
                    backup_file, new_remote,
                )
            except Exception as err:
                _LOGGER.warning("Failed to rename backup on FTP: %s", err)

    # Step 5: Delete backup from server if requested
    if not keep_on_server:
        try:
            def ftp_delete():
                ftp = ftplib.FTP()
                ftp.connect(ftp_host, ftp_port, timeout=30)
                ftp.login(ftp_user, ftp_password)
                try:
                    ftp.delete(backup_file)
                    _LOGGER.info("Deleted backup from server: %s", backup_file)
                finally:
                    try:
                        ftp.quit()
                    except Exception:
                        ftp.close()

            await hass.async_add_executor_job(ftp_delete)
        except Exception as err:
            _LOGGER.warning("Failed to delete backup from server: %s", err)

    # Step 6: Cleanup old backups (retention)
    await async_cleanup_old_backups(
        hass, ftp_host, ftp_port, ftp_user, ftp_password,
        remote_dir, destination_path, retention_days,
    )

    # Fire success event
    hass.bus.async_fire("multicraft_backup_completed", {
        "server_id": server_id,
        "file": downloaded_path,
    })

    # Refresh coordinator
    await coordinator.async_request_refresh()

    return downloaded_path


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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry to new version."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version < 3:
        new_data = {**config_entry.data}
        if CONF_FTP_PASSWORD not in new_data:
            new_data[CONF_FTP_PASSWORD] = ""
        hass.config_entries.async_update_entry(config_entry, data=new_data, version=3)

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True


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

                # Fetch backup status conditionally
                backup_active = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("backup_active", set())
                if server_id in backup_active:
                    try:
                        backup_result = await api.get_server_backup_status(int(server_id))
                        backup_data = backup_result.get("data", {})
                        server_data["backup_status"] = backup_data.get("status", "unknown")
                        server_data["backup_file"] = backup_data.get("file", "")
                        server_data["backup_ftp"] = backup_data.get("ftp", "")
                        server_data["backup_message"] = backup_data.get("message", "")
                        server_data["backup_time"] = backup_data.get("time", "")

                        # If backup is no longer running, remove from active set
                        if backup_data.get("status") not in ("running", None):
                            backup_active.discard(server_id)
                    except Exception as backup_err:
                        _LOGGER.warning("Error fetching backup status for server %s: %s", server_id, backup_err)
                        server_data["backup_status"] = "error"
                        server_data["backup_file"] = ""
                        server_data["backup_ftp"] = ""
                        server_data["backup_message"] = ""
                        server_data["backup_time"] = ""
                else:
                    server_data["backup_status"] = "idle"
                    server_data["backup_file"] = ""
                    server_data["backup_ftp"] = ""
                    server_data["backup_message"] = ""
                    server_data["backup_time"] = ""

                data[server_id] = server_data
            except Exception as err:
                _LOGGER.error("Error fetching data for server %s: %s", server_id, err)
                data[server_id] = {
                    "status": "unknown",
                    "server_name": servers_info.get(server_id, f"Server {server_id}"),
                    "error": str(err),
                    "latency": None,
                    "version": None,
                    "backup_status": "idle",
                    "backup_file": "",
                    "backup_ftp": "",
                    "backup_message": "",
                    "backup_time": "",
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
        "backup_active": set(),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register download_backup service (only once)
    if not hass.services.has_service(DOMAIN, "download_backup"):

        SERVICE_DOWNLOAD_BACKUP_SCHEMA = vol.Schema({
            vol.Required("device_id"): cv.string,
            vol.Optional("destination_path"): cv.string,
        }, extra=vol.ALLOW_EXTRA)

        async def handle_download_backup(call):
            """Handle the download_backup service call."""
            # Resolve device_id to server_id and entry_id
            device_id = call.data.get("device_id")
            if not device_id:
                raise HomeAssistantError(
                    "No target device specified. Please select a Minecraft server device."
                )

            device_registry = dr.async_get(hass)
            device = device_registry.async_get(device_id)
            if not device:
                raise HomeAssistantError("Target device not found")

            # Extract server_id from device identifiers
            # Format: (DOMAIN, "{entry_id}_{server_id}")
            server_id = None
            entry_id = None
            for identifier in device.identifiers:
                if identifier[0] == DOMAIN:
                    # Split "{entry_id}_{server_id}" - entry_id is hex (no underscores)
                    parts = identifier[1].rsplit("_", 1)
                    if len(parts) == 2:
                        entry_id = parts[0]
                        server_id = parts[1]
                    break

            if not server_id or not entry_id:
                raise HomeAssistantError("Could not resolve server from target device")

            # Find the entry data and config entry
            target_entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
            if target_entry_data is None:
                raise HomeAssistantError(f"Server {server_id} not found in any Multicraft config entry")

            target_config_entry = None
            for ce in hass.config_entries.async_entries(DOMAIN):
                if ce.entry_id == entry_id:
                    target_config_entry = ce
                    break

            api_instance = target_entry_data["api"]
            coordinator_instance = target_entry_data["coordinator"]

            # Get ftp_password from config entry data
            ftp_password = ""
            if target_config_entry:
                ftp_password = target_config_entry.data.get(CONF_FTP_PASSWORD, "")

            # Get backup options from config entry
            options = target_config_entry.options if target_config_entry else {}
            default_destination = options.get(CONF_DEFAULT_DESTINATION, "")
            rotation_enabled = options.get(CONF_BACKUP_ROTATION, DEFAULT_BACKUP_ROTATION)
            retention_days = int(options.get(CONF_BACKUP_RETENTION_DAYS, DEFAULT_BACKUP_RETENTION_DAYS))
            keep_on_server = options.get(CONF_KEEP_BACKUP_ON_SERVER, DEFAULT_KEEP_BACKUP_ON_SERVER)

            # Service can override destination via call data
            destination_path = call.data.get("destination_path") or default_destination
            if not destination_path:
                destination_path = "/media/multicraft_backups/"

            backup_active = target_entry_data.get("backup_active", set())

            await async_backup_and_download(
                hass, api_instance, server_id, ftp_password, destination_path,
                rotation_enabled, retention_days, keep_on_server,
                backup_active, coordinator_instance,
            )

        hass.services.async_register(
            DOMAIN,
            "download_backup",
            handle_download_backup,
            schema=SERVICE_DOWNLOAD_BACKUP_SCHEMA,
        )

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    # Unregister service if no entries remain
    if not hass.data.get(DOMAIN):
        if hass.services.has_service(DOMAIN, "download_backup"):
            hass.services.async_remove(DOMAIN, "download_backup")

    return unload_ok
