"""
Configuration Manager

Handles loading, saving, and validation of sensor configuration stored in
sensors.json. Provides a simple interface for reading and writing sensor MAC
addresses and calibration data so that the last-used sensors are remembered
across application restarts.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict[str, Any] = {
    "sensors": {
        "heart_rate": {
            "type": "polar_h10",
            "mac_address": "",
            "name": "Polar Heart Rate Monitor",
        },
        "power_meter": {
            "type": "stages",
            "mac_address": "",
            "name": "Power Meter",
        },
        "trainer": {
            "type": "elite_muin_plus",
            "mac_address": "",
            "name": "Elite Real Turbo Muin+",
        },
    },
    "calibration": {
        "power_offset": 0.0,
        "last_calibrated": "",
    },
    "athlete": {
        "ftp": 250,
        "max_hr": 185,
        "weight_kg": 75.0,
    },
}


class ConfigManager:
    """Manages sensor configuration stored in a JSON file.

    Attributes:
        config_path: Absolute path to the sensors.json file.
        config: The in-memory configuration dictionary.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Initialise the config manager.

        Args:
            config_path: Path to the sensors.json file.  If *None*, the file
                ``config/sensors.json`` relative to the project root is used.
        """
        if config_path is None:
            project_root = Path(__file__).parent.parent
            config_path = str(project_root / "config" / "sensors.json")

        self.config_path = config_path
        self.config: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_sensor_mac(self, sensor_type: str) -> str:
        """Return the stored MAC address for *sensor_type*.

        Args:
            sensor_type: One of ``"heart_rate"``, ``"power_meter"``,
                ``"trainer"``.

        Returns:
            The MAC address string, or an empty string when not set.
        """
        return self.config.get("sensors", {}).get(sensor_type, {}).get("mac_address", "")

    def set_sensor_mac(self, sensor_type: str, mac_address: str) -> None:
        """Persist the MAC address for *sensor_type* to disk.

        Args:
            sensor_type: One of ``"heart_rate"``, ``"power_meter"``,
                ``"trainer"``.
            mac_address: BLE MAC address string (e.g. ``"AA:BB:CC:DD:EE:FF"``).
        """
        if "sensors" not in self.config:
            self.config["sensors"] = {}
        if sensor_type not in self.config["sensors"]:
            self.config["sensors"][sensor_type] = {}
        self.config["sensors"][sensor_type]["mac_address"] = mac_address
        self._save()
        logger.info("Saved MAC address for %s: %s", sensor_type, mac_address)

    def get_sensor_name(self, sensor_type: str) -> str:
        """Return the human-readable device name for *sensor_type*.

        Args:
            sensor_type: One of ``"heart_rate"``, ``"power_meter"``,
                ``"trainer"``.

        Returns:
            The device name string, or an empty string when not set.
        """
        return self.config.get("sensors", {}).get(sensor_type, {}).get("name", "")

    def set_sensor_name(self, sensor_type: str, name: str) -> None:
        """Persist the device name for *sensor_type* to disk.

        Args:
            sensor_type: Sensor key.
            name: Human-readable device name.
        """
        if "sensors" not in self.config:
            self.config["sensors"] = {}
        if sensor_type not in self.config["sensors"]:
            self.config["sensors"][sensor_type] = {}
        self.config["sensors"][sensor_type]["name"] = name
        self._save()

    def get_power_offset(self) -> float:
        """Return the calibration power offset (watts).

        Returns:
            Power offset as a float; defaults to ``0.0``.
        """
        return float(self.config.get("calibration", {}).get("power_offset", 0.0))

    def set_power_offset(self, offset: float) -> None:
        """Persist the calibration power offset to disk.

        Args:
            offset: Power offset in watts.
        """
        if "calibration" not in self.config:
            self.config["calibration"] = {}
        self.config["calibration"]["power_offset"] = offset
        self.config["calibration"]["last_calibrated"] = datetime.now().isoformat()
        self._save()
        logger.info("Saved power offset: %.2f W", offset)

    def get_last_calibrated(self) -> str:
        """Return the ISO-8601 timestamp of the last calibration.

        Returns:
            Timestamp string, or ``""`` when never calibrated.
        """
        return self.config.get("calibration", {}).get("last_calibrated", "")

    # ------------------------------------------------------------------
    # Athlete settings
    # ------------------------------------------------------------------

    def get_ftp(self) -> int:
        """Return the athlete's functional threshold power (watts).

        Returns:
            FTP in watts; defaults to ``250``.
        """
        return int(self.config.get("athlete", {}).get("ftp", 250))

    def set_ftp(self, ftp: int) -> None:
        """Persist the athlete's FTP to disk.

        Args:
            ftp: Functional threshold power in watts.
        """
        if "athlete" not in self.config:
            self.config["athlete"] = {}
        self.config["athlete"]["ftp"] = max(1, int(ftp))
        self._save()
        logger.info("Saved FTP: %d W", ftp)

    def get_max_hr(self) -> int:
        """Return the athlete's maximum heart rate (BPM).

        Returns:
            Max HR in BPM; defaults to ``185``.
        """
        return int(self.config.get("athlete", {}).get("max_hr", 185))

    def get_weight_kg(self) -> float:
        """Return the athlete's body weight in kilograms.

        Returns:
            Weight in kg; defaults to ``75.0``.
        """
        return float(self.config.get("athlete", {}).get("weight_kg", 75.0))

    def reload(self) -> None:
        """Re-read the configuration from disk."""
        self._load()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load configuration from disk; fall back to defaults on error."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                self.config = self._merge_defaults(loaded)
                logger.info("Loaded config from %s", self.config_path)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read config (%s); using defaults", exc)
                self.config = json.loads(json.dumps(DEFAULT_CONFIG))
        else:
            logger.info("Config file not found – creating defaults at %s", self.config_path)
            self.config = json.loads(json.dumps(DEFAULT_CONFIG))
            self._save()

    def _save(self) -> None:
        """Write the current configuration to disk."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as fh:
                json.dump(self.config, fh, indent=2, ensure_ascii=False)
            logger.debug("Config saved to %s", self.config_path)
        except OSError as exc:
            logger.error("Failed to save config: %s", exc)

    @staticmethod
    def _merge_defaults(loaded: dict[str, Any]) -> dict[str, Any]:
        """Deep-merge *loaded* on top of ``DEFAULT_CONFIG``.

        This ensures new keys introduced by future versions of the app are
        always present even when an older config file is read.

        Args:
            loaded: Config dictionary read from disk.

        Returns:
            Merged configuration dictionary.
        """
        result: dict[str, Any] = json.loads(json.dumps(DEFAULT_CONFIG))
        for key, value in loaded.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key].update(value)
            else:
                result[key] = value
        return result
