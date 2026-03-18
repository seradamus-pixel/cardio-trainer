"""
Device Manager

Manages saved BLE devices and training-threshold configuration (LTHR, FTP).
Persists data to ``config/devices.json``.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG: Dict[str, Any] = {
    "devices": [],
    "lthr": 0,
    "ftp": 0,
    "last_updated": "",
}


class DeviceManager:
    """Manages saved BLE devices and training configuration.

    Attributes:
        config_path: Absolute path to ``devices.json``.
        config: In-memory configuration dictionary.

    Example::

        manager = DeviceManager()
        manager.add_device("AA:BB:CC:DD:EE:FF", "Polar H10", "heart_rate_monitor")
        manager.set_lthr(155)
        manager.set_ftp(250)
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Initialise the device manager.

        Args:
            config_path: Path to ``devices.json``.  If *None*, defaults to
                ``config/devices.json`` relative to the project root.
        """
        if config_path is None:
            project_root = Path(__file__).parent.parent
            config_path = str(project_root / "config" / "devices.json")

        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------

    def get_devices(self) -> List[Dict[str, str]]:
        """Return the list of saved devices."""
        return list(self.config.get("devices", []))

    def add_device(self, address: str, name: str, device_type: str) -> bool:
        """Add a device to the saved list.

        Args:
            address: BLE MAC address (e.g. ``"AA:BB:CC:DD:EE:FF"``).
            name: Human-readable device name.
            device_type: One of ``"heart_rate_monitor"``, ``"trainer"``,
                ``"unknown"``.

        Returns:
            ``True`` if the device was added; ``False`` if it was already
            present (identified by *address*).
        """
        devices = self.get_devices()
        for d in devices:
            if d.get("address") == address:
                logger.info("Device %s is already saved.", address)
                return False
        devices.append({"name": name, "address": address, "type": device_type})
        self.config["devices"] = devices
        self._save()
        logger.info("Added device: %s (%s)", name, address)
        return True

    def remove_device(self, address: str) -> bool:
        """Remove a saved device by MAC address.

        Args:
            address: BLE MAC address.

        Returns:
            ``True`` if the device was found and removed; ``False`` otherwise.
        """
        devices = self.get_devices()
        new_devices = [d for d in devices if d.get("address") != address]
        if len(new_devices) == len(devices):
            logger.info("Device %s not found in saved list.", address)
            return False
        self.config["devices"] = new_devices
        self._save()
        logger.info("Removed device: %s", address)
        return True

    # ------------------------------------------------------------------
    # Training thresholds
    # ------------------------------------------------------------------

    def get_lthr(self) -> int:
        """Return the Lactate Threshold Heart Rate value (bpm)."""
        return int(self.config.get("lthr", 0))

    def set_lthr(self, value: int) -> None:
        """Persist the LTHR value.

        Args:
            value: Heart rate at lactate threshold in bpm (must be ≥ 0).

        Raises:
            ValueError: If *value* is negative.
        """
        if value < 0:
            raise ValueError(f"LTHR must be non-negative, got {value}")
        self.config["lthr"] = value
        self._save()
        logger.info("LTHR set to %d bpm", value)

    def get_ftp(self) -> int:
        """Return the Functional Threshold Power value (watts)."""
        return int(self.config.get("ftp", 0))

    def set_ftp(self, value: int) -> None:
        """Persist the FTP value.

        Args:
            value: Functional Threshold Power in watts (must be ≥ 0).

        Raises:
            ValueError: If *value* is negative.
        """
        if value < 0:
            raise ValueError(f"FTP must be non-negative, got {value}")
        self.config["ftp"] = value
        self._save()
        logger.info("FTP set to %d W", value)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load configuration from disk; fall back to defaults on error."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                self.config = {**_DEFAULT_CONFIG, **loaded}
                logger.info("Loaded config from %s", self.config_path)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read config (%s); using defaults.", exc)
                self.config = dict(_DEFAULT_CONFIG)
        else:
            logger.info("Config file not found – creating at %s", self.config_path)
            self.config = dict(_DEFAULT_CONFIG)
            self._save()

    def _save(self) -> None:
        """Write the current configuration to disk."""
        self.config["last_updated"] = datetime.now().isoformat()
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as fh:
                json.dump(self.config, fh, indent=2, ensure_ascii=False)
            logger.debug("Config saved to %s", self.config_path)
        except OSError as exc:
            logger.error("Failed to save config: %s", exc)
