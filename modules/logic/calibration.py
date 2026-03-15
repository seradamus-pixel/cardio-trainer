"""
Power Meter Calibration

Guides the user through a static zero-offset calibration procedure for a
strain-gauge power meter (e.g. Stages, Quarq, etc.).

Protocol:
  1. Ensure the rider is off the bike and the crank arm hangs freely.
  2. Send a calibration-request write to the Cycling Power Control Point
     characteristic (0x2A66).
  3. Wait for the Cycling Power Control Point response indicating success
     and the raw zero-offset value.
  4. Persist the resulting offset via ConfigManager.

The class emits PyQt5 signals so the UI can display progress without
blocking.
"""

import asyncio
import logging
import struct
from typing import Optional

from bleak import BleakClient, BleakError
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from config.config_manager import ConfigManager

logger = logging.getLogger(__name__)

_POWER_CONTROL_POINT_CHAR = "00002a66-0000-1000-8000-00805f9b34fb"
_POWER_FEATURE_CHAR = "00002a65-0000-1000-8000-00805f9b34fb"

# Op-codes (Cycling Power Control Point)
_OP_REQUEST_CALIBRATION = 0x01
_OP_RESPONSE_CODE = 0x20
_RESPONSE_SUCCESS = 0x01


class CalibrationState:
    IDLE = "idle"
    REQUESTING = "requesting"
    WAITING = "waiting"
    SUCCESS = "success"
    FAILED = "failed"


class _CalibrationWorker(QThread):
    """Background thread that performs the BLE calibration handshake."""

    progress = pyqtSignal(str)           # status message
    finished = pyqtSignal(bool, float)   # (success, offset_watts)
    error = pyqtSignal(str)

    def __init__(
        self,
        mac_address: str,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.mac_address = mac_address

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._calibrate())
        except Exception as exc:
            logger.exception("Calibration error: %s", exc)
            self.error.emit(str(exc))
            self.finished.emit(False, 0.0)
        finally:
            loop.close()

    async def _calibrate(self) -> None:
        self.progress.emit("Connecting to power meter…")
        async with BleakClient(self.mac_address) as client:
            self.progress.emit("Connected. Requesting calibration…")

            response_event = asyncio.Event()
            offset: list[float] = [0.0]
            success_flag: list[bool] = [False]

            def _cp_handler(_: int, data: bytearray) -> None:
                if len(data) < 3:
                    return
                if data[0] == _OP_RESPONSE_CODE and data[1] == _OP_REQUEST_CALIBRATION:
                    if data[2] == _RESPONSE_SUCCESS and len(data) >= 5:
                        raw = struct.unpack_from("<h", data, 3)[0]
                        offset[0] = raw / 1000.0  # mW → W
                        success_flag[0] = True
                    response_event.set()

            try:
                await client.start_notify(_POWER_CONTROL_POINT_CHAR, _cp_handler)
            except BleakError as exc:
                self.error.emit(f"Control Point not available: {exc}")
                self.finished.emit(False, 0.0)
                return

            # Send calibration request
            try:
                await client.write_gatt_char(
                    _POWER_CONTROL_POINT_CHAR,
                    bytearray([_OP_REQUEST_CALIBRATION]),
                    response=True,
                )
            except BleakError as exc:
                self.error.emit(f"Failed to send calibration request: {exc}")
                self.finished.emit(False, 0.0)
                return

            self.progress.emit("Waiting for zero-offset response (up to 30 s)…")
            try:
                await asyncio.wait_for(response_event.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                self.error.emit("Calibration timed out – no response from device.")
                self.finished.emit(False, 0.0)
                return
            finally:
                try:
                    await client.stop_notify(_POWER_CONTROL_POINT_CHAR)
                except BleakError:
                    pass

            if success_flag[0]:
                self.progress.emit(
                    f"Calibration successful! Zero offset: {offset[0]:.3f} W"
                )
                self.finished.emit(True, offset[0])
            else:
                self.error.emit("Device reported calibration failure.")
                self.finished.emit(False, 0.0)


class PowerMeterCalibration(QObject):
    """High-level power-meter calibration controller.

    Signals:
        calibration_progress: Human-readable status message.
        calibration_complete: Emitted with ``(success, offset_watts)`` when
            the procedure finishes.
        calibration_error: Emitted with an error message string.

    Example::

        cal = PowerMeterCalibration(config_manager)
        cal.calibration_complete.connect(my_slot)
        cal.start_calibration("AA:BB:CC:DD:EE:FF")
    """

    calibration_progress = pyqtSignal(str)
    calibration_complete = pyqtSignal(bool, float)
    calibration_error = pyqtSignal(str)

    def __init__(
        self,
        config_manager: ConfigManager,
        parent: Optional[QObject] = None,
    ) -> None:
        """Initialise the calibration controller.

        Args:
            config_manager: Used to persist the resulting offset on success.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._config_manager = config_manager
        self._worker: Optional[_CalibrationWorker] = None
        self.state = CalibrationState.IDLE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_calibration(self, mac_address: str) -> None:
        """Begin the calibration procedure for the device at *mac_address*.

        Calibration is performed in a background thread so the UI is not
        blocked.  Make sure the bike is stationary and the crank is hanging
        freely before calling this method.

        Args:
            mac_address: BLE MAC address of the power meter.
        """
        if self._worker and self._worker.isRunning():
            logger.warning("Calibration already in progress")
            return

        self.state = CalibrationState.REQUESTING
        self._worker = _CalibrationWorker(mac_address=mac_address)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self.calibration_error)
        self._worker.start()
        logger.info("Calibration started for %s", mac_address)

    def cancel(self) -> None:
        """Abort an in-progress calibration."""
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(3000)
        self.state = CalibrationState.IDLE

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _on_progress(self, message: str) -> None:
        self.state = CalibrationState.WAITING
        self.calibration_progress.emit(message)

    def _on_finished(self, success: bool, offset: float) -> None:
        if success:
            self.state = CalibrationState.SUCCESS
            self._config_manager.set_power_offset(offset)
            logger.info("Power offset saved: %.3f W", offset)
        else:
            self.state = CalibrationState.FAILED
        self.calibration_complete.emit(success, offset)
