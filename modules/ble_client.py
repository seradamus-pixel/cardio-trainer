"""
BLE Client

Unified BLE interface for the training application.  Wraps
:class:`~modules.connection.device_manager.DeviceManager` (heart rate monitor
and power meter) and :class:`~modules.trainer.control.TrainerControl` (smart
trainer) into a single object that the training screen can connect to.

Data flow
---------
- HR monitor  → ``DeviceManager`` → ``hr_updated`` signal
- Power meter → ``DeviceManager`` → ``power_updated`` / ``cadence_updated``
- Trainer     → ``TrainerControl`` → ``power_updated`` / ``cadence_updated``
  (Indoor Bike Data characteristic, FTMS)
- Trainer FTMS control commands are sent via :meth:`set_target_power` and
  :meth:`set_resistance`.
"""

import logging
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

from modules.connection.device_manager import DeviceManager
from modules.trainer.control import BikeData, TrainerControl

logger = logging.getLogger(__name__)


class BLEClient(QObject):
    """Unified BLE client for HR monitor, power meter, and smart trainer.

    Signals:
        hr_updated: Emitted with heart rate in BPM.
        power_updated: Emitted with power in watts.
        cadence_updated: Emitted with cadence in RPM.
        hr_battery_updated: Emitted with HR monitor battery percent.
        trainer_battery_updated: Emitted with trainer battery percent.
        sensor_connected: Emitted with the device role string when connected.
        sensor_disconnected: Emitted with the device role string on disconnect.
        error: Emitted with a human-readable error message string.

    Example::

        client = BLEClient()
        client.hr_updated.connect(screen.update_hr)
        client.connect_hr_sensor("AA:BB:CC:DD:EE:FF")
        client.connect_trainer("11:22:33:44:55:66")
        client.set_target_power(200)
    """

    hr_updated = pyqtSignal(int)
    power_updated = pyqtSignal(int)
    cadence_updated = pyqtSignal(float)
    hr_battery_updated = pyqtSignal(int)
    trainer_battery_updated = pyqtSignal(int)
    sensor_connected = pyqtSignal(str)      # role string
    sensor_disconnected = pyqtSignal(str)   # role string
    error = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._device_manager = DeviceManager(self)
        self._trainer_control = TrainerControl(self)
        self._connected_roles: set[str] = set()

        # DeviceManager signals
        self._device_manager.connected.connect(self._on_device_connected)
        self._device_manager.disconnected.connect(self._on_device_disconnected)
        self._device_manager.heart_rate_updated.connect(self.hr_updated)
        self._device_manager.power_updated.connect(self.power_updated)
        self._device_manager.cadence_updated.connect(self.cadence_updated)
        self._device_manager.battery_updated.connect(self._on_battery_updated)
        self._device_manager.connection_error.connect(
            lambda mac, msg: self.error.emit(f"{mac}: {msg}")
        )

        # TrainerControl signals
        self._trainer_control.connected.connect(
            lambda: self._on_role_connected("trainer")
        )
        self._trainer_control.disconnected.connect(
            lambda: self._on_role_disconnected("trainer")
        )
        self._trainer_control.data_updated.connect(self._on_trainer_data)
        self._trainer_control.error.connect(self.error)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect_hr_sensor(self, mac_address: str) -> None:
        """Connect to the heart rate monitor at *mac_address*.

        Args:
            mac_address: BLE MAC address string.
        """
        if not mac_address:
            logger.warning("HR sensor MAC address not configured")
            return
        logger.info("Connecting to HR sensor: %s", mac_address)
        self._device_manager.connect_device(mac_address, "heart_rate")

    def connect_power_meter(self, mac_address: str) -> None:
        """Connect to the power meter at *mac_address*.

        Args:
            mac_address: BLE MAC address string.
        """
        if not mac_address:
            logger.warning("Power meter MAC address not configured")
            return
        logger.info("Connecting to power meter: %s", mac_address)
        self._device_manager.connect_device(mac_address, "power_meter")

    def connect_trainer(self, mac_address: str) -> None:
        """Connect to the smart trainer at *mac_address*.

        Also requests FTMS control so that :meth:`set_target_power` and
        :meth:`set_resistance` commands are accepted.

        Args:
            mac_address: BLE MAC address string.
        """
        if not mac_address:
            logger.warning("Trainer MAC address not configured")
            return
        logger.info("Connecting to trainer: %s", mac_address)
        self._trainer_control.connect_trainer(mac_address)

    def disconnect_all(self) -> None:
        """Disconnect all sensors and the trainer gracefully."""
        self._device_manager.disconnect_all()
        self._trainer_control.disconnect_trainer()
        self._connected_roles.clear()

    # ------------------------------------------------------------------
    # Trainer control
    # ------------------------------------------------------------------

    def set_target_power(self, watts: int) -> None:
        """Switch the trainer to ERG mode and hold *watts*.

        Args:
            watts: Target power in watts (0–2000).
        """
        self._trainer_control.set_target_power(watts)

    def set_resistance(self, level: int) -> None:
        """Switch the trainer to resistance mode.

        Args:
            level: Resistance level 0–100 (percent of maximum).
        """
        self._trainer_control.set_resistance(level)

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_connected(self, role: str) -> bool:
        """Return whether the device for *role* is currently connected.

        Args:
            role: One of ``"heart_rate"``, ``"power_meter"``, ``"trainer"``.
        """
        return role in self._connected_roles

    @property
    def trainer_control(self) -> TrainerControl:
        """Direct access to the underlying :class:`TrainerControl`."""
        return self._trainer_control

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _on_device_connected(self, _mac: str, role: str) -> None:
        self._connected_roles.add(role)
        self.sensor_connected.emit(role)
        logger.info("BLEClient: %s connected", role)

    def _on_device_disconnected(self, _mac: str, role: str) -> None:
        self._connected_roles.discard(role)
        self.sensor_disconnected.emit(role)
        logger.info("BLEClient: %s disconnected", role)

    def _on_role_connected(self, role: str) -> None:
        self._connected_roles.add(role)
        self.sensor_connected.emit(role)
        logger.info("BLEClient: %s connected", role)

    def _on_role_disconnected(self, role: str) -> None:
        self._connected_roles.discard(role)
        self.sensor_disconnected.emit(role)
        logger.info("BLEClient: %s disconnected", role)

    def _on_battery_updated(self, role: str, percent: int) -> None:
        if role == "heart_rate":
            self.hr_battery_updated.emit(percent)
        elif role in ("trainer", "power_meter"):
            self.trainer_battery_updated.emit(percent)

    def _on_trainer_data(self, bike_data: BikeData) -> None:
        """Forward Indoor Bike Data to the unified power/cadence signals."""
        if bike_data.power_w > 0:
            self.power_updated.emit(bike_data.power_w)
        if bike_data.cadence_rpm >= 0:
            self.cadence_updated.emit(bike_data.cadence_rpm)
        if bike_data.heart_rate_bpm > 0:
            self.hr_updated.emit(bike_data.heart_rate_bpm)
