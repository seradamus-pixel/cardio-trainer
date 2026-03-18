"""
BLE Scanner

Discovers nearby Bluetooth Low Energy devices using *bleak* and asyncio.
Identifies device types (Heart Rate Monitor / Trainer) from BLE service UUIDs.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

logger = logging.getLogger(__name__)

# Standard BLE service UUIDs
_HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
_POWER_SERVICE_UUID = "00001818-0000-1000-8000-00805f9b34fb"
_FITNESS_MACHINE_UUID = "00001826-0000-1000-8000-00805f9b34fb"

# Used when the advertisement data carries no RSSI; -127 is the minimum
# representable value in the signed-byte RSSI field of the BLE spec.
_RSSI_UNAVAILABLE = -127

DEVICE_TYPE_HR = "heart_rate_monitor"
DEVICE_TYPE_TRAINER = "trainer"
DEVICE_TYPE_UNKNOWN = "unknown"

_TYPE_LABELS: Dict[str, str] = {
    DEVICE_TYPE_HR: "Pulsometr",
    DEVICE_TYPE_TRAINER: "Trenażer",
    DEVICE_TYPE_UNKNOWN: "Nieznany",
}


@dataclass
class ScannedDevice:
    """Snapshot of a discovered BLE device."""

    address: str
    name: str
    rssi: int
    service_uuids: List[str] = field(default_factory=list)

    @property
    def device_type(self) -> str:
        """Determine device type from BLE service UUIDs."""
        uuids = [u.lower() for u in self.service_uuids]
        if _HR_SERVICE_UUID in uuids:
            return DEVICE_TYPE_HR
        if _POWER_SERVICE_UUID in uuids or _FITNESS_MACHINE_UUID in uuids:
            return DEVICE_TYPE_TRAINER
        return DEVICE_TYPE_UNKNOWN

    def device_type_label(self) -> str:
        """Human-readable Polish device type label."""
        return _TYPE_LABELS.get(self.device_type, "Nieznany")


async def scan_devices(
    duration: float = 10.0,
    on_device_found: Optional[Callable[[ScannedDevice], None]] = None,
) -> List[ScannedDevice]:
    """Scan for nearby BLE devices and return the results.

    Args:
        duration: How long to scan in seconds.
        on_device_found: Optional callback invoked each time a new or updated
            device is discovered during the scan.

    Returns:
        List of :class:`ScannedDevice` objects sorted by RSSI (strongest first).
    """
    logger.info("Starting BLE scan (%.1f s)...", duration)
    seen: Dict[str, ScannedDevice] = {}

    def _callback(device: BLEDevice, adv: AdvertisementData) -> None:
        info = ScannedDevice(
            address=device.address,
            name=device.name or adv.local_name or "Unknown",
            rssi=adv.rssi if adv.rssi is not None else _RSSI_UNAVAILABLE,
            service_uuids=list(adv.service_uuids or []),
        )
        is_new = device.address not in seen
        rssi_changed = not is_new and seen[device.address].rssi != info.rssi
        if is_new or rssi_changed:
            seen[device.address] = info
            if on_device_found is not None:
                on_device_found(info)

    async with BleakScanner(detection_callback=_callback):
        await asyncio.sleep(duration)

    devices = list(seen.values())
    logger.info("Scan complete. Found %d device(s).", len(devices))
    return sorted(devices, key=lambda d: d.rssi, reverse=True)
