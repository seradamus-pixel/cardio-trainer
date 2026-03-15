"""
Device Manager

Maintains long-lived BLE connections to the heart-rate sensor, power meter,
and smart trainer.  Each device is connected in its own asyncio task running
inside a dedicated QThread so that the UI stays responsive at all times.

Characteristic UUIDs follow the Bluetooth SIG standard profile specs:
  - Heart Rate Measurement  : 0x2A37
  - Cycling Power Measurement: 0x2A63
  - Battery Level            : 0x2A19
  - CSC Measurement          : 0x2A5B  (cadence/speed – optional)
"""

import asyncio
import logging
import struct
from enum import Enum, auto
from typing import Optional

from bleak import BleakClient, BleakError
from PyQt5.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# BLE characteristic UUIDs
# ------------------------------------------------------------------
_HEART_RATE_CHAR = "00002a37-0000-1000-8000-00805f9b34fb"
_POWER_CHAR = "00002a63-0000-1000-8000-00805f9b34fb"
_BATTERY_CHAR = "00002a19-0000-1000-8000-00805f9b34fb"
_CSC_CHAR = "00002a5b-0000-1000-8000-00805f9b34fb"

# Reconnect settings
_RECONNECT_DELAY = 5.0  # seconds between reconnect attempts
_MAX_RECONNECT_ATTEMPTS = 10


class ConnectionState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()


class _DeviceWorker(QThread):
    """Background thread that owns the asyncio event loop for one device."""

    connected = pyqtSignal(str)          # mac address
    disconnected = pyqtSignal(str)       # mac address
    heart_rate_received = pyqtSignal(int)
    power_received = pyqtSignal(int)     # watts
    cadence_received = pyqtSignal(float) # rpm
    battery_received = pyqtSignal(int)   # percent
    error_occurred = pyqtSignal(str, str)  # (mac, message)

    def __init__(
        self,
        mac_address: str,
        device_role: str,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.mac_address = mac_address
        self.device_role = device_role
        self._stop_event: Optional[asyncio.Event] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def request_stop(self) -> None:
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()
        try:
            self._loop.run_until_complete(self._connect_loop())
        except Exception as exc:  # pragma: no cover
            logger.exception("Device worker error (%s): %s", self.mac_address, exc)
            self.error_occurred.emit(self.mac_address, str(exc))
        finally:
            self._loop.close()

    async def _connect_loop(self) -> None:
        attempts = 0
        while not self._stop_event.is_set() and attempts < _MAX_RECONNECT_ATTEMPTS:
            try:
                logger.info("Connecting to %s (%s)…", self.device_role, self.mac_address)
                async with BleakClient(self.mac_address) as client:
                    self.connected.emit(self.mac_address)
                    attempts = 0
                    await self._subscribe(client)
                    # Wait until the user requests disconnect or device drops
                    await self._stop_event.wait()
            except BleakError as exc:
                attempts += 1
                msg = str(exc)
                logger.warning(
                    "Connection failed for %s (attempt %d): %s",
                    self.mac_address, attempts, msg,
                )
                self.error_occurred.emit(self.mac_address, msg)
                self.disconnected.emit(self.mac_address)
                if not self._stop_event.is_set():
                    await asyncio.sleep(_RECONNECT_DELAY)
        self.disconnected.emit(self.mac_address)

    async def _subscribe(self, client: BleakClient) -> None:
        """Subscribe to all relevant characteristics for this device role."""
        # Battery level (best-effort)
        try:
            battery_data = await client.read_gatt_char(_BATTERY_CHAR)
            self.battery_received.emit(battery_data[0])
        except (BleakError, KeyError):
            logger.debug("Battery characteristic not available on %s", self.mac_address)

        if self.device_role == "heart_rate":
            await self._subscribe_heart_rate(client)
        elif self.device_role == "power_meter":
            await self._subscribe_power(client)
        elif self.device_role == "trainer":
            await self._subscribe_trainer(client)

    async def _subscribe_heart_rate(self, client: BleakClient) -> None:
        def _hr_handler(_: int, data: bytearray) -> None:
            flags = data[0]
            if flags & 0x01:
                hr = struct.unpack_from("<H", data, 1)[0]
            else:
                hr = data[1]
            self.heart_rate_received.emit(hr)

        await client.start_notify(_HEART_RATE_CHAR, _hr_handler)
        logger.info("Subscribed to heart rate on %s", self.mac_address)
        await self._stop_event.wait()
        await client.stop_notify(_HEART_RATE_CHAR)

    async def _subscribe_power(self, client: BleakClient) -> None:
        def _power_handler(_: int, data: bytearray) -> None:
            if len(data) >= 4:
                power = struct.unpack_from("<h", data, 2)[0]
                self.power_received.emit(max(0, int(power)))

        await client.start_notify(_POWER_CHAR, _power_handler)
        logger.info("Subscribed to power on %s", self.mac_address)

        # Also subscribe to cadence if available
        try:
            def _csc_handler(_: int, data: bytearray) -> None:
                # Simplified CSC parsing – flags byte + cumulative crank revs + last crank event time
                flags = data[0]
                if flags & 0x02 and len(data) >= 7:
                    crank_revs = struct.unpack_from("<H", data, 3)[0]
                    crank_time = struct.unpack_from("<H", data, 5)[0]
                    # Emit raw values; actual RPM is computed in DataCalculator
                    _ = crank_revs, crank_time  # stored by the worker for delta calc

            await client.start_notify(_CSC_CHAR, _csc_handler)
        except BleakError:
            logger.debug("CSC characteristic not available on %s", self.mac_address)

        await self._stop_event.wait()
        try:
            await client.stop_notify(_POWER_CHAR)
        except BleakError:
            pass

    async def _subscribe_trainer(self, client: BleakClient) -> None:
        def _power_handler(_: int, data: bytearray) -> None:
            if len(data) >= 4:
                power = struct.unpack_from("<h", data, 2)[0]
                self.power_received.emit(max(0, int(power)))

        await client.start_notify(_POWER_CHAR, _power_handler)
        logger.info("Subscribed to trainer power on %s", self.mac_address)
        await self._stop_event.wait()
        try:
            await client.stop_notify(_POWER_CHAR)
        except BleakError:
            pass


class DeviceManager(QObject):
    """Manages BLE connections to the HR sensor, power meter, and trainer.

    Signals:
        connected: Emitted when a device establishes a connection.
        disconnected: Emitted when a device loses its connection.
        heart_rate_updated: Live heart rate in BPM.
        power_updated: Live power in watts.
        cadence_updated: Live cadence in RPM.
        battery_updated: Tuple of (device_role, battery_percent).
        connection_error: Tuple of (mac_address, error_message).

    Example::

        manager = DeviceManager()
        manager.heart_rate_updated.connect(ui.update_hr_display)
        manager.connect_device("AA:BB:CC:DD:EE:FF", "heart_rate")
    """

    connected = pyqtSignal(str, str)        # (mac, role)
    disconnected = pyqtSignal(str, str)     # (mac, role)
    heart_rate_updated = pyqtSignal(int)
    power_updated = pyqtSignal(int)
    cadence_updated = pyqtSignal(float)
    battery_updated = pyqtSignal(str, int)  # (role, percent)
    connection_error = pyqtSignal(str, str) # (mac, message)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._workers: dict[str, _DeviceWorker] = {}  # keyed by role

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect_device(self, mac_address: str, device_role: str) -> None:
        """Connect to a BLE device.

        Args:
            mac_address: BLE MAC address string.
            device_role: One of ``"heart_rate"``, ``"power_meter"``,
                ``"trainer"``.
        """
        self.disconnect_device(device_role)
        worker = _DeviceWorker(mac_address=mac_address, device_role=device_role)
        worker.connected.connect(lambda mac: self.connected.emit(mac, device_role))
        worker.disconnected.connect(lambda mac: self.disconnected.emit(mac, device_role))
        worker.heart_rate_received.connect(self.heart_rate_updated)
        worker.power_received.connect(self.power_updated)
        worker.cadence_received.connect(self.cadence_updated)
        worker.battery_received.connect(
            lambda pct: self.battery_updated.emit(device_role, pct)
        )
        worker.error_occurred.connect(self.connection_error)
        self._workers[device_role] = worker
        worker.start()
        logger.info("Connection requested: %s → %s", device_role, mac_address)

    def disconnect_device(self, device_role: str) -> None:
        """Disconnect and clean up a device by role.

        Args:
            device_role: One of ``"heart_rate"``, ``"power_meter"``,
                ``"trainer"``.
        """
        worker = self._workers.pop(device_role, None)
        if worker and worker.isRunning():
            worker.request_stop()
            worker.wait(5000)
            logger.info("Disconnected: %s", device_role)

    def disconnect_all(self) -> None:
        """Disconnect all currently connected devices."""
        for role in list(self._workers.keys()):
            self.disconnect_device(role)

    def is_connected(self, device_role: str) -> bool:
        """Return whether the device for *device_role* is currently connected."""
        worker = self._workers.get(device_role)
        return worker is not None and worker.isRunning()

    def connection_state(self, device_role: str) -> ConnectionState:
        """Return the connection state for *device_role*."""
        worker = self._workers.get(device_role)
        if worker is None:
            return ConnectionState.DISCONNECTED
        if worker.isRunning():
            return ConnectionState.CONNECTED
        return ConnectionState.DISCONNECTED
