"""
BLE Scanner

Discovers nearby Bluetooth Low Energy devices using *bleak* and emits
real-time signal-strength (RSSI) and advertisement data through PyQt5
signals so that the UI can populate the sensor-selection drop-downs without
blocking the main thread.
"""

import asyncio
import logging
from typing import Callable, Optional

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from PyQt5.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger(__name__)

# Standard BLE service UUIDs used to classify devices
_HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
_POWER_SERVICE_UUID = "00001818-0000-1000-8000-00805f9b34fb"
_FITNESS_MACHINE_UUID = "00001826-0000-1000-8000-00805f9b34fb"
_BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"


class DeviceInfo:
    """Snapshot of a discovered BLE device."""

    def __init__(
        self,
        address: str,
        name: str,
        rssi: int,
        service_uuids: list[str],
        battery_level: Optional[int] = None,
    ) -> None:
        self.address = address
        self.name = name or "Unknown"
        self.rssi = rssi
        self.service_uuids = [u.lower() for u in service_uuids]
        self.battery_level = battery_level

    @property
    def is_heart_rate_sensor(self) -> bool:
        return _HR_SERVICE_UUID in self.service_uuids

    @property
    def is_power_meter(self) -> bool:
        return _POWER_SERVICE_UUID in self.service_uuids

    @property
    def is_fitness_machine(self) -> bool:
        return _FITNESS_MACHINE_UUID in self.service_uuids

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"DeviceInfo(name={self.name!r}, address={self.address!r}, "
            f"rssi={self.rssi} dBm)"
        )


class _ScanWorker(QThread):
    """Background thread that runs an async BLE scan loop."""

    device_found = pyqtSignal(object)   # emits DeviceInfo
    scan_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        scan_duration: float = 10.0,
        device_filter: Optional[Callable[[DeviceInfo], bool]] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._scan_duration = scan_duration
        self._device_filter = device_filter
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:  # noqa: D401
        """Entry point for the QThread – executes the async scan."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._scan())
        except Exception as exc:
            logger.exception("BLE scan error: %s", exc)
            self.error_occurred.emit(str(exc))
        finally:
            loop.close()
        self.scan_finished.emit()

    async def _scan(self) -> None:
        seen: dict[str, DeviceInfo] = {}

        def _callback(device: BLEDevice, adv: AdvertisementData) -> None:
            if self._stop_requested:
                return
            info = DeviceInfo(
                address=device.address,
                name=device.name or adv.local_name or "",
                rssi=adv.rssi if adv.rssi is not None else -127,
                service_uuids=list(adv.service_uuids or []),
            )
            if self._device_filter and not self._device_filter(info):
                return
            if device.address not in seen or seen[device.address].rssi != info.rssi:
                seen[device.address] = info
                self.device_found.emit(info)

        async with BleakScanner(detection_callback=_callback):
            elapsed = 0.0
            step = 0.2
            while elapsed < self._scan_duration and not self._stop_requested:
                await asyncio.sleep(step)
                elapsed += step


class BLEScanner(QObject):
    """High-level BLE scanner that integrates with the PyQt5 event loop.

    Signals:
        device_discovered: Emitted for each new or updated device found.
        scan_complete: Emitted when the scan finishes normally.
        error: Emitted with an error message string if scanning fails.

    Example::

        scanner = BLEScanner()
        scanner.device_discovered.connect(my_slot)
        scanner.start_scan()
    """

    device_discovered = pyqtSignal(object)  # DeviceInfo
    scan_complete = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        scan_duration: float = 10.0,
        device_filter: Optional[Callable[[DeviceInfo], bool]] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        """Initialise the scanner.

        Args:
            scan_duration: How long (seconds) to scan for devices.
            device_filter: Optional predicate; only devices for which the
                function returns ``True`` will be emitted.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._scan_duration = scan_duration
        self._device_filter = device_filter
        self._worker: Optional[_ScanWorker] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_scan(self) -> None:
        """Begin a BLE discovery scan in a background thread.

        If a scan is already running it is stopped first.
        """
        self.stop_scan()
        logger.info("Starting BLE scan (duration=%.1f s)", self._scan_duration)
        self._worker = _ScanWorker(
            scan_duration=self._scan_duration,
            device_filter=self._device_filter,
        )
        self._worker.device_found.connect(self.device_discovered)
        self._worker.scan_finished.connect(self.scan_complete)
        self._worker.error_occurred.connect(self.error)
        self._worker.start()

    def stop_scan(self) -> None:
        """Abort any in-progress scan."""
        if self._worker and self._worker.isRunning():
            logger.info("Stopping BLE scan")
            self._worker.request_stop()
            self._worker.wait(3000)
        self._worker = None

    @property
    def is_scanning(self) -> bool:
        """Return ``True`` while a background scan is active."""
        return self._worker is not None and self._worker.isRunning()
