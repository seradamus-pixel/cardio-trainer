"""
Trainer UI

Main application window for the training session.  Wires together:

- :class:`~modules.ui.training_screen.TrainingScreen` – the large-display UI
- :class:`~modules.ble_client.BLEClient` – BLE sensor connections
- :class:`~modules.power_controller.PowerController` – ERG / Resistance logic
- :class:`~modules.data_recorder.SessionRecorder` – workout data persistence

Configuration is loaded from ``config/sensors.json`` via
:class:`~config.config_manager.ConfigManager`.  MAC addresses stored there are
used to auto-connect to the configured sensors on startup.
"""

import logging
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QWidget,
)

from config.config_manager import ConfigManager
from modules.ble_client import BLEClient
from modules.data_recorder import SessionRecorder
from modules.power_controller import ControlMode, PowerController
from modules.ui.styles import APP_STYLESHEET
from modules.ui.training_screen import TrainingScreen

logger = logging.getLogger(__name__)

# How often (ms) to record a data sample to the session file
_SAMPLE_INTERVAL_MS = 1000


class TrainerUI(QMainWindow):
    """Main QMainWindow for the live training session.

    On construction the window:
    1. Reads sensor MAC addresses and athlete settings from ``sensors.json``.
    2. Attempts to connect to each configured sensor.
    3. Wires BLE data signals to the :class:`TrainingScreen`.
    4. Starts a 1-second recording timer.

    Args:
        config: Optional :class:`ConfigManager` instance.  A default one
            (reading ``config/sensors.json``) is created when ``None``.
        parent: Optional parent widget.

    Example::

        app = QApplication(sys.argv)
        app.setStyleSheet(APP_STYLESHEET)
        window = TrainerUI()
        window.show()
        sys.exit(app.exec_())
    """

    def __init__(
        self,
        config: Optional[ConfigManager] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config or ConfigManager()

        # Read athlete settings from config
        ftp = self._config.get_ftp()
        max_hr = self._config.get_max_hr()
        weight_kg = self._config.get_weight_kg()
        logger.info(
            "Athlete settings: FTP=%d W, max HR=%d, weight=%.1f kg",
            ftp, max_hr, weight_kg,
        )

        # Build sub-components
        self._ble_client = BLEClient(self)
        self._power_ctrl = PowerController(ble_client=self._ble_client, parent=self)
        self._recorder = SessionRecorder(ftp=ftp)

        # Build UI
        self._screen = TrainingScreen(ftp=ftp, parent=self)
        self.setCentralWidget(self._screen)
        self._build_status_bar()

        # Timers
        self._sample_timer = QTimer(self)
        self._sample_timer.setInterval(_SAMPLE_INTERVAL_MS)
        self._sample_timer.timeout.connect(self._record_sample)
        self._sample_timer.start()

        # Wire signals
        self._wire_signals()

        # Window appearance
        self.setWindowTitle("trainero2 – Sesja treningowa")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        # Auto-connect to configured devices
        QTimer.singleShot(500, self._auto_connect)

    # ------------------------------------------------------------------
    # Window setup helpers
    # ------------------------------------------------------------------

    def _build_status_bar(self) -> None:
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Łączenie z czujnikami… / Connecting to sensors…")

    def _wire_signals(self) -> None:
        # BLE → screen
        self._ble_client.hr_updated.connect(self._screen.update_hr)
        self._ble_client.power_updated.connect(self._screen.update_power)
        self._ble_client.cadence_updated.connect(self._screen.update_cadence)
        self._ble_client.hr_battery_updated.connect(self._screen.on_hr_battery)
        self._ble_client.trainer_battery_updated.connect(self._screen.on_trainer_battery)
        self._ble_client.sensor_connected.connect(self._screen.on_sensor_connected)
        self._ble_client.sensor_disconnected.connect(self._screen.on_sensor_disconnected)
        self._ble_client.sensor_connected.connect(self._on_sensor_connected)
        self._ble_client.sensor_disconnected.connect(self._on_sensor_disconnected)
        self._ble_client.error.connect(self._on_ble_error)

        # Cadence → power controller (auto mode switching)
        self._ble_client.cadence_updated.connect(self._on_cadence_for_controller)

        # Power controller mode changes → screen label
        self._power_ctrl.mode_changed.connect(self._on_mode_changed)

        # Apply button → set power
        self._screen.apply_button.clicked.connect(self._on_apply_power)

        # Trainer reconnection → re-apply mode
        self._ble_client.sensor_connected.connect(self._on_trainer_reconnected)

    # ------------------------------------------------------------------
    # Device auto-connect
    # ------------------------------------------------------------------

    def _auto_connect(self) -> None:
        """Read MAC addresses from config and connect to each sensor."""
        hr_mac = self._config.get_sensor_mac("heart_rate")
        trainer_mac = self._config.get_sensor_mac("trainer")
        power_mac = self._config.get_sensor_mac("power_meter")

        connected_any = False

        if hr_mac:
            logger.info("Auto-connecting HR sensor: %s", hr_mac)
            self._ble_client.connect_hr_sensor(hr_mac)
            connected_any = True
        else:
            logger.warning("No HR sensor MAC in config – skipping")
            self._status_bar.showMessage(
                "⚠  Brak adresu MAC pulsometru w konfiguracji"
            )

        if trainer_mac:
            logger.info("Auto-connecting trainer: %s", trainer_mac)
            self._ble_client.connect_trainer(trainer_mac)
            connected_any = True
        elif power_mac:
            logger.info("Auto-connecting power meter: %s", power_mac)
            self._ble_client.connect_power_meter(power_mac)
            connected_any = True
        else:
            logger.warning("No trainer or power meter MAC in config – skipping")

        if not connected_any:
            self._status_bar.showMessage(
                "⚠  Brak skonfigurowanych czujników – uruchom najpierw konfigurację"
            )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _on_apply_power(self) -> None:
        watts = self._screen.watts_spinbox.value()
        self._power_ctrl.set_target_power(watts)
        logger.info("Applied target power: %d W", watts)
        self._status_bar.showMessage(f"Cel mocy ustawiony: {watts} W")

    @pyqtSlot(float)
    def _on_cadence_for_controller(self, rpm: float) -> None:
        self._power_ctrl.update_cadence(rpm)

    @pyqtSlot(object)
    def _on_mode_changed(self, mode: ControlMode) -> None:
        if mode == ControlMode.ERG:
            self._screen.set_mode_label("ERG", is_erg=True)
            self._status_bar.showMessage("Tryb ERG – stała moc")
        else:
            self._screen.set_mode_label("RESISTANCE", is_erg=False)
            self._status_bar.showMessage(
                "Tryb oporu – niska kadencja, zmniejszono opór"
            )

    @pyqtSlot(str)
    def _on_sensor_connected(self, role: str) -> None:
        names = {
            "heart_rate": "Pulsometr",
            "trainer": "Trenażer",
            "power_meter": "Miernik mocy",
        }
        self._status_bar.showMessage(
            f"✓  Połączono: {names.get(role, role)}"
        )

    @pyqtSlot(str)
    def _on_sensor_disconnected(self, role: str) -> None:
        names = {
            "heart_rate": "Pulsometr",
            "trainer": "Trenażer",
            "power_meter": "Miernik mocy",
        }
        self._status_bar.showMessage(
            f"✗  Rozłączono: {names.get(role, role)} – ponawiam połączenie…"
        )

    @pyqtSlot(str)
    def _on_trainer_reconnected(self, role: str) -> None:
        if role == "trainer":
            # Re-apply the current power mode after reconnection
            QTimer.singleShot(1000, self._power_ctrl.apply_current_mode)

    @pyqtSlot(str)
    def _on_ble_error(self, message: str) -> None:
        logger.error("BLE error: %s", message)
        self._status_bar.showMessage(f"⚠  BLE błąd: {message}")

    @pyqtSlot()
    def _record_sample(self) -> None:
        """Called every second: records one training sample."""
        # Only record when the session timer is running (cadence > 0)
        if self._screen.elapsed_seconds > 0:
            if not self._recorder.is_active:
                self._recorder.start()
            self._recorder.add_sample(
                hr=self._screen.current_hr,
                power=self._screen.current_power,
                cadence=self._screen.current_cadence,
            )

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def _save_session(self) -> None:
        if self._recorder.is_active and self._recorder.elapsed_seconds > 10:
            try:
                summary = self._recorder.stop()
                path = self._recorder.save(summary)
                logger.info("Session saved to %s", path)
                QMessageBox.information(
                    self,
                    "Trening zapisany",
                    f"Dane sesji zapisano w:\n{path}",
                )
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to save session: %s", exc)

    # ------------------------------------------------------------------
    # Qt event overrides
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_session()
        self._sample_timer.stop()
        self._ble_client.disconnect_all()
        event.accept()
