"""
Elite Muin+ Trainer Control

Implements the FTMS (Fitness Machine Service) control protocol for the
Elite Real Turbo Muin+ smart trainer.  Supports:
  - ERG mode: hold a specific target power
  - Resistance mode: set a percentage brake load
  - Simulation mode: set virtual road gradient/wind speed/CdA/Crr

Service UUID  : 00001826-0000-1000-8000-00805f9b34fb (Fitness Machine)
Characteristic UUIDs:
  - Indoor Bike Data      : 00002ad2-0000-1000-8000-00805f9b34fb
  - Fitness Machine Status: 00002ada-0000-1000-8000-00805f9b34fb
  - FM Control Point      : 00002ad9-0000-1000-8000-00805f9b34fb
"""

import asyncio
import logging
import struct
from enum import Enum, auto
from typing import Optional

from bleak import BleakClient, BleakError
from PyQt5.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger(__name__)

_FM_CONTROL_POINT = "00002ad9-0000-1000-8000-00805f9b34fb"
_INDOOR_BIKE_DATA = "00002ad2-0000-1000-8000-00805f9b34fb"
_FM_STATUS = "00002ada-0000-1000-8000-00805f9b34fb"

# FTMS Control Point op-codes
_OP_REQUEST_CONTROL = 0x00
_OP_RESET = 0x01
_OP_SET_TARGET_POWER = 0x05
_OP_SET_TARGET_RESISTANCE = 0x04
_OP_SET_INDOOR_BIKE_SIMULATION = 0x11
_OP_RESPONSE = 0x80
_RESULT_SUCCESS = 0x01


class TrainerMode(Enum):
    ERG = auto()
    RESISTANCE = auto()
    SIMULATION = auto()


class BikeData:
    """Snapshot of data received from the Indoor Bike Data characteristic."""

    __slots__ = ("speed_kmh", "cadence_rpm", "power_w", "heart_rate_bpm")

    def __init__(
        self,
        speed_kmh: float = 0.0,
        cadence_rpm: float = 0.0,
        power_w: int = 0,
        heart_rate_bpm: int = 0,
    ) -> None:
        self.speed_kmh = speed_kmh
        self.cadence_rpm = cadence_rpm
        self.power_w = power_w
        self.heart_rate_bpm = heart_rate_bpm

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"BikeData(speed={self.speed_kmh:.1f} km/h, "
            f"cadence={self.cadence_rpm:.0f} rpm, "
            f"power={self.power_w} W)"
        )


class _TrainerWorker(QThread):
    """Background thread that maintains the BLE connection to the trainer."""

    connected = pyqtSignal()
    disconnected = pyqtSignal()
    data_received = pyqtSignal(object)   # BikeData
    error_occurred = pyqtSignal(str)
    control_accepted = pyqtSignal(bool)  # True = success

    def __init__(
        self,
        mac_address: str,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.mac_address = mac_address
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._client: Optional[BleakClient] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._command_queue: Optional[asyncio.Queue] = None

    def request_stop(self) -> None:
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)

    def enqueue_command(self, data: bytes) -> None:
        """Thread-safe enqueue of a raw FTMS control command."""
        if self._loop and self._command_queue:
            self._loop.call_soon_threadsafe(self._command_queue.put_nowait, data)

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()
        self._command_queue = asyncio.Queue()
        try:
            self._loop.run_until_complete(self._connect_loop())
        except Exception as exc:
            logger.exception("Trainer worker error: %s", exc)
            self.error_occurred.emit(str(exc))
        finally:
            self._loop.close()

    async def _connect_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                logger.info("Connecting to trainer %s…", self.mac_address)
                async with BleakClient(self.mac_address) as client:
                    self._client = client
                    self.connected.emit()
                    await self._setup(client)
                    await asyncio.gather(
                        self._command_dispatcher(client),
                        self._stop_event.wait(),
                    )
            except BleakError as exc:
                logger.warning("Trainer connection error: %s", exc)
                self.error_occurred.emit(str(exc))
                self.disconnected.emit()
                if not self._stop_event.is_set():
                    await asyncio.sleep(5.0)
        self.disconnected.emit()

    async def _setup(self, client: BleakClient) -> None:
        # Subscribe to indoor bike data
        def _bike_handler(_: int, data: bytearray) -> None:
            bd = _parse_indoor_bike_data(data)
            self.data_received.emit(bd)

        await client.start_notify(_INDOOR_BIKE_DATA, _bike_handler)

        # Request FTMS control
        await client.write_gatt_char(
            _FM_CONTROL_POINT,
            bytearray([_OP_REQUEST_CONTROL]),
            response=True,
        )
        logger.info("FTMS control granted for %s", self.mac_address)

    async def _command_dispatcher(self, client: BleakClient) -> None:
        while not self._stop_event.is_set():
            try:
                cmd = await asyncio.wait_for(self._command_queue.get(), timeout=1.0)
                await client.write_gatt_char(_FM_CONTROL_POINT, cmd, response=True)
                self.control_accepted.emit(True)
            except asyncio.TimeoutError:
                continue
            except BleakError as exc:
                logger.warning("Failed to send control command: %s", exc)
                self.control_accepted.emit(False)


def _parse_indoor_bike_data(data: bytearray) -> BikeData:
    """Parse the Indoor Bike Data characteristic payload.

    The flags field (first two bytes) indicates which optional fields are
    present.  We decode up to speed, cadence, power, and HR.
    """
    bd = BikeData()
    if len(data) < 2:
        return bd
    flags = struct.unpack_from("<H", data)[0]
    offset = 2

    # Bit 0: More Data (inverse: bit clear means speed present)
    if not (flags & 0x0001) and len(data) >= offset + 2:
        bd.speed_kmh = struct.unpack_from("<H", data, offset)[0] / 100.0
        offset += 2

    # Bit 1: Average Speed present
    if flags & 0x0002:
        offset += 2

    # Bit 2: Instantaneous Cadence present
    if flags & 0x0004 and len(data) >= offset + 2:
        bd.cadence_rpm = struct.unpack_from("<H", data, offset)[0] / 2.0
        offset += 2

    # Bit 3: Average Cadence present
    if flags & 0x0008:
        offset += 2

    # Bit 4: Total Distance present
    if flags & 0x0010:
        offset += 3

    # Bit 5: Resistance Level present
    if flags & 0x0020:
        offset += 2

    # Bit 6: Instantaneous Power present
    if flags & 0x0040 and len(data) >= offset + 2:
        bd.power_w = struct.unpack_from("<h", data, offset)[0]
        offset += 2

    # Bit 7: Average Power present
    if flags & 0x0080:
        offset += 2

    # Bit 8: Expanded Energy present (3 bytes)
    if flags & 0x0100:
        offset += 3

    # Bit 9: Heart Rate present
    if flags & 0x0200 and len(data) >= offset + 1:
        bd.heart_rate_bpm = data[offset]

    return bd


class TrainerControl(QObject):
    """High-level interface for controlling the Elite Real Turbo Muin+.

    Signals:
        connected: Emitted when the trainer connects successfully.
        disconnected: Emitted when the trainer disconnects.
        data_updated: Emitted with a BikeData snapshot on each notification.
        command_result: Emitted with ``True`` when a command is accepted.
        error: Emitted with an error message string.

    Example::

        trainer = TrainerControl()
        trainer.data_updated.connect(ui.update_trainer_display)
        trainer.connect_trainer("AA:BB:CC:DD:EE:FF")
        trainer.set_target_power(200)
    """

    connected = pyqtSignal()
    disconnected = pyqtSignal()
    data_updated = pyqtSignal(object)  # BikeData
    command_result = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[_TrainerWorker] = None
        self._mode: TrainerMode = TrainerMode.ERG
        self._target_power: int = 0

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect_trainer(self, mac_address: str) -> None:
        """Connect to the trainer at *mac_address*.

        Args:
            mac_address: BLE MAC address of the Elite Muin+ trainer.
        """
        self.disconnect_trainer()
        self._worker = _TrainerWorker(mac_address=mac_address)
        self._worker.connected.connect(self.connected)
        self._worker.disconnected.connect(self.disconnected)
        self._worker.data_received.connect(self.data_updated)
        self._worker.error_occurred.connect(self.error)
        self._worker.control_accepted.connect(self.command_result)
        self._worker.start()
        logger.info("Trainer connection requested: %s", mac_address)

    def disconnect_trainer(self) -> None:
        """Disconnect from the trainer."""
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.wait(5000)
        self._worker = None

    @property
    def is_connected(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    # ------------------------------------------------------------------
    # Control commands
    # ------------------------------------------------------------------

    def set_target_power(self, watts: int) -> None:
        """Send an ERG-mode target power command.

        Args:
            watts: Target power in watts (0–2000).
        """
        watts = max(0, min(2000, int(watts)))
        self._mode = TrainerMode.ERG
        self._target_power = watts
        payload = struct.pack("<Bh", _OP_SET_TARGET_POWER, watts)
        self._send(payload)
        logger.debug("Set target power: %d W", watts)

    def set_resistance(self, level: int) -> None:
        """Send a resistance-mode command.

        Args:
            level: Resistance level 0–100 (percent of maximum).
        """
        level = max(0, min(100, int(level)))
        self._mode = TrainerMode.RESISTANCE
        # FTMS resistance level is in 0.1 % units, range 0–1000
        payload = struct.pack("<BH", _OP_SET_TARGET_RESISTANCE, level * 10)
        self._send(payload)
        logger.debug("Set resistance level: %d %%", level)

    def set_simulation(
        self,
        wind_speed: float = 0.0,
        grade: float = 0.0,
        crr: float = 0.004,
        cw: float = 0.51,
    ) -> None:
        """Send a simulation-mode command.

        Args:
            wind_speed: Wind speed in m/s (−32.767 to +32.767).
            grade: Road gradient in % (−100 to +100).
            crr: Coefficient of rolling resistance (0–0.0254).
            cw: Wind resistance coefficient in kg/m (0–1.524).
        """
        self._mode = TrainerMode.SIMULATION
        wind_speed_raw = int(round(wind_speed * 1000))   # 0.001 m/s units
        grade_raw = int(round(grade * 100))              # 0.01 % units
        crr_raw = int(round(crr * 10000))                # 0.0001 units
        cw_raw = int(round(cw * 100))                    # 0.01 kg/m units
        payload = struct.pack(
            "<BhhBB",
            _OP_SET_INDOOR_BIKE_SIMULATION,
            wind_speed_raw,
            grade_raw,
            crr_raw,
            cw_raw,
        )
        self._send(payload)
        logger.debug(
            "Set simulation: wind=%.2f m/s, grade=%.1f %%, crr=%.4f, cw=%.2f",
            wind_speed, grade, crr, cw,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _send(self, payload: bytes) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.enqueue_command(payload)
        else:
            logger.warning("Command ignored – trainer not connected")
