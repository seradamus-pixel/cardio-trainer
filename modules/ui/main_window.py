"""
Main Window

PyQt5 main application window with a three-panel layout:

  Left panel   – Heart rate sensor (Polar H10)
                 • Device drop-down populated by BLE scan
                 • Battery level, RSSI indicator
                 • Live heart rate display + zone badge
                 • "Continue" button (enabled once a device is connected)

  Centre panel – Power meter (Stages, etc.)
                 • Device drop-down populated by BLE scan
                 • Battery level, RSSI indicator
                 • Live power display
                 • Status label prompting pedal activation

  Right panel  – Smart trainer (Elite Real Turbo Muin+)
                 • Device drop-down populated by BLE scan
                 • Live speed / cadence / power display
                 • ERG-mode power target slider
                 • Simulation-mode gradient slider
"""

import logging
from typing import Optional

from PyQt5.QtCore import QTimer, Qt, pyqtSlot
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from config.config_manager import ConfigManager
from modules.connection.ble_scanner import BLEScanner, DeviceInfo
from modules.connection.device_manager import DeviceManager
from modules.logic.calculations import DataCalculator
from modules.logic.calibration import PowerMeterCalibration
from modules.trainer.control import BikeData, TrainerControl
from modules.ui.styles import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_RED,
    APP_STYLESHEET,
    TEXT_SECONDARY,
)
from modules.ui.widgets import (
    BatteryIndicator,
    MetricDisplay,
    PowerSlider,
    RSSIBar,
    ScanButton,
    ZoneIndicator,
)

logger = logging.getLogger(__name__)


class _SensorPanel(QFrame):
    """Base class for a sensor panel frame."""

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("sensorPanel")
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(280)

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(16, 16, 16, 16)
        self._root_layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        self._root_layout.addWidget(title_label)

    def _make_row(self, label_text: str, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setObjectName("statusLabel")
        lbl.setFixedWidth(90)
        row.addWidget(lbl)
        row.addWidget(widget)
        row.addStretch()
        return row


class _HRPanel(_SensorPanel):
    """Left panel – heart rate sensor."""

    def __init__(
        self,
        scanner: BLEScanner,
        device_manager: DeviceManager,
        config_manager: ConfigManager,
        calculator: DataCalculator,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__("❤  Heart Rate Sensor", parent)
        self._scanner = scanner
        self._dm = device_manager
        self._config = config_manager
        self._calc = calculator
        self._devices: dict[str, DeviceInfo] = {}
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        # Scan controls
        self._scan_btn = ScanButton()
        self._root_layout.addWidget(self._scan_btn)

        self._combo = QComboBox()
        self._combo.addItem("-- Select device --", None)
        self._combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._root_layout.addWidget(self._combo)

        # Status indicators
        indicator_row = QHBoxLayout()
        self._battery = BatteryIndicator()
        self._rssi_bar = RSSIBar()
        self._battery_label = QLabel("Bat: --")
        self._battery_label.setObjectName("statusLabel")
        self._rssi_label = QLabel("RSSI: -- dBm")
        self._rssi_label.setObjectName("statusLabel")
        indicator_row.addWidget(self._battery)
        indicator_row.addWidget(self._battery_label)
        indicator_row.addSpacing(12)
        indicator_row.addWidget(self._rssi_bar)
        indicator_row.addWidget(self._rssi_label)
        indicator_row.addStretch()
        self._root_layout.addLayout(indicator_row)

        # Live display
        self._hr_display = MetricDisplay("Heart Rate", "BPM")
        self._hr_display.setMinimumHeight(100)
        self._root_layout.addWidget(self._hr_display)

        # Zone badge
        zone_row = QHBoxLayout()
        _zone_lbl = QLabel("Zone:")
        _zone_lbl.setObjectName("statusLabel")
        zone_row.addWidget(_zone_lbl)
        self._zone = ZoneIndicator(zone_type="hr")
        zone_row.addWidget(self._zone)
        zone_row.addStretch()
        self._root_layout.addLayout(zone_row)

        # Connection status
        self._status_label = QLabel("Not connected")
        self._status_label.setObjectName("statusLabel")
        self._root_layout.addWidget(self._status_label)

        # Continue button
        self._continue_btn = QPushButton("Continue →")
        self._continue_btn.setObjectName("successButton")
        self._continue_btn.setEnabled(False)
        self._root_layout.addWidget(self._continue_btn)

        self._root_layout.addStretch()

    def _connect_signals(self) -> None:
        self._scan_btn.scan_requested.connect(self._start_scan)
        self._scan_btn.stop_requested.connect(self._stop_scan)
        self._combo.currentIndexChanged.connect(self._on_device_selected)

        self._scanner.device_discovered.connect(self._on_device_found)
        self._scanner.scan_complete.connect(lambda: self._scan_btn.set_scanning(False))

        self._dm.heart_rate_updated.connect(self._on_hr_update)
        self._dm.battery_updated.connect(self._on_battery_update)
        self._dm.connected.connect(self._on_connected)
        self._dm.disconnected.connect(self._on_disconnected)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _start_scan(self) -> None:
        self._devices.clear()
        self._combo.clear()
        self._combo.addItem("-- Select device --", None)
        self._scanner.start_scan()
        self._scan_btn.set_scanning(True)
        self._status_label.setText("Scanning…")

    @pyqtSlot()
    def _stop_scan(self) -> None:
        self._scanner.stop_scan()
        self._scan_btn.set_scanning(False)
        self._status_label.setText("Scan stopped")

    @pyqtSlot(object)
    def _on_device_found(self, info: DeviceInfo) -> None:
        if not info.is_heart_rate_sensor:
            return
        self._devices[info.address] = info
        label = f"{info.name} ({info.address})  [{info.rssi} dBm]"
        # Remove and re-add to keep list fresh
        for i in range(1, self._combo.count()):
            if self._combo.itemData(i) == info.address:
                self._combo.setItemText(i, label)
                return
        self._combo.addItem(label, info.address)

    @pyqtSlot(int)
    def _on_device_selected(self, index: int) -> None:
        mac = self._combo.itemData(index)
        if mac:
            self._status_label.setText(f"Connecting to {mac}…")
            self._dm.connect_device(mac, "heart_rate")
            self._config.set_sensor_mac("heart_rate", mac)
            if mac in self._devices:
                info = self._devices[mac]
                self._rssi_bar.set_rssi(info.rssi)
                self._rssi_label.setText(f"RSSI: {info.rssi} dBm")

    @pyqtSlot(int)
    def _on_hr_update(self, bpm: int) -> None:
        self._calc.add_hr_sample(bpm)
        self._hr_display.set_value(bpm)
        zone_num, zone_name = self._calc.hr_zone(bpm)
        self._zone.set_zone(zone_num, zone_name)
        from modules.ui.styles import zone_color
        self._hr_display.set_color(zone_color(zone_num, "hr"))

    @pyqtSlot(str, int)
    def _on_battery_update(self, role: str, pct: int) -> None:
        if role == "heart_rate":
            self._battery.set_level(pct)
            self._battery_label.setText(f"Bat: {pct} %")

    @pyqtSlot(str, str)
    def _on_connected(self, _mac: str, role: str) -> None:
        if role == "heart_rate":
            self._status_label.setText("✅ Connected")
            self._status_label.setStyleSheet(f"color: {ACCENT_GREEN};")
            self._continue_btn.setEnabled(True)

    @pyqtSlot(str, str)
    def _on_disconnected(self, _mac: str, role: str) -> None:
        if role == "heart_rate":
            self._status_label.setText("Disconnected")
            self._status_label.setStyleSheet(f"color: {ACCENT_RED};")
            self._continue_btn.setEnabled(False)
            self._hr_display.reset()
            self._zone.reset()


class _PowerPanel(_SensorPanel):
    """Centre panel – power meter sensor."""

    def __init__(
        self,
        scanner: BLEScanner,
        device_manager: DeviceManager,
        config_manager: ConfigManager,
        calibration: PowerMeterCalibration,
        calculator: DataCalculator,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__("⚡  Power Meter", parent)
        self._scanner = scanner
        self._dm = device_manager
        self._config = config_manager
        self._calibration = calibration
        self._calc = calculator
        self._devices: dict[str, DeviceInfo] = {}
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        self._scan_btn = ScanButton()
        self._root_layout.addWidget(self._scan_btn)

        self._combo = QComboBox()
        self._combo.addItem("-- Select device --", None)
        self._combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._root_layout.addWidget(self._combo)

        # Status indicators
        indicator_row = QHBoxLayout()
        self._battery = BatteryIndicator()
        self._rssi_bar = RSSIBar()
        self._battery_label = QLabel("Bat: --")
        self._battery_label.setObjectName("statusLabel")
        self._rssi_label = QLabel("RSSI: -- dBm")
        self._rssi_label.setObjectName("statusLabel")
        indicator_row.addWidget(self._battery)
        indicator_row.addWidget(self._battery_label)
        indicator_row.addSpacing(12)
        indicator_row.addWidget(self._rssi_bar)
        indicator_row.addWidget(self._rssi_label)
        indicator_row.addStretch()
        self._root_layout.addLayout(indicator_row)

        # Live power display
        self._power_display = MetricDisplay("Power", "Watts")
        self._power_display.setMinimumHeight(100)
        self._root_layout.addWidget(self._power_display)

        # Zone badge + W/kg row
        meta_row = QHBoxLayout()
        self._zone = ZoneIndicator(zone_type="power")
        self._wpkg_label = QLabel("-- W/kg")
        self._wpkg_label.setObjectName("statusLabel")
        _zone_lbl2 = QLabel("Zone:")
        _zone_lbl2.setObjectName("statusLabel")
        meta_row.addWidget(_zone_lbl2)
        meta_row.addWidget(self._zone)
        meta_row.addSpacing(20)
        meta_row.addWidget(self._wpkg_label)
        meta_row.addStretch()
        self._root_layout.addLayout(meta_row)

        # Pedal-activation prompt
        self._pedal_label = QLabel("🚴 Start pedalling to activate sensor")
        self._pedal_label.setObjectName("statusLabel")
        self._pedal_label.setAlignment(Qt.AlignCenter)
        self._root_layout.addWidget(self._pedal_label)

        # Status + calibration
        self._status_label = QLabel("Not connected")
        self._status_label.setObjectName("statusLabel")
        self._root_layout.addWidget(self._status_label)

        self._cal_btn = QPushButton("Calibrate Zero Offset")
        self._cal_btn.setEnabled(False)
        self._cal_btn.setObjectName("dangerButton")
        self._root_layout.addWidget(self._cal_btn)

        self._root_layout.addStretch()

    def _connect_signals(self) -> None:
        self._scan_btn.scan_requested.connect(self._start_scan)
        self._scan_btn.stop_requested.connect(self._stop_scan)
        self._combo.currentIndexChanged.connect(self._on_device_selected)
        self._cal_btn.clicked.connect(self._start_calibration)

        self._scanner.device_discovered.connect(self._on_device_found)
        self._scanner.scan_complete.connect(lambda: self._scan_btn.set_scanning(False))

        self._dm.power_updated.connect(self._on_power_update)
        self._dm.battery_updated.connect(self._on_battery_update)
        self._dm.connected.connect(self._on_connected)
        self._dm.disconnected.connect(self._on_disconnected)

        self._calibration.calibration_progress.connect(
            lambda msg: self._status_label.setText(msg)
        )
        self._calibration.calibration_complete.connect(self._on_calibration_done)
        self._calibration.calibration_error.connect(
            lambda msg: self._status_label.setText(f"⚠ {msg}")
        )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _start_scan(self) -> None:
        self._devices.clear()
        self._combo.clear()
        self._combo.addItem("-- Select device --", None)
        self._scanner.start_scan()
        self._scan_btn.set_scanning(True)

    @pyqtSlot()
    def _stop_scan(self) -> None:
        self._scanner.stop_scan()
        self._scan_btn.set_scanning(False)

    @pyqtSlot(object)
    def _on_device_found(self, info: DeviceInfo) -> None:
        if not info.is_power_meter:
            return
        self._devices[info.address] = info
        label = f"{info.name} ({info.address})  [{info.rssi} dBm]"
        for i in range(1, self._combo.count()):
            if self._combo.itemData(i) == info.address:
                self._combo.setItemText(i, label)
                return
        self._combo.addItem(label, info.address)

    @pyqtSlot(int)
    def _on_device_selected(self, index: int) -> None:
        mac = self._combo.itemData(index)
        if mac:
            self._dm.connect_device(mac, "power_meter")
            self._config.set_sensor_mac("power_meter", mac)
            if mac in self._devices:
                info = self._devices[mac]
                self._rssi_bar.set_rssi(info.rssi)
                self._rssi_label.setText(f"RSSI: {info.rssi} dBm")

    @pyqtSlot(int)
    def _on_power_update(self, watts: int) -> None:
        self._calc.add_power_sample(watts)
        self._power_display.set_value(watts)
        zone_num, zone_name = self._calc.power_zone(watts)
        self._zone.set_zone(zone_num, zone_name)
        from modules.ui.styles import zone_color
        self._power_display.set_color(zone_color(zone_num, "power"))
        self._wpkg_label.setText(f"{self._calc.watts_per_kg():.2f} W/kg")
        self._pedal_label.setVisible(False)

    @pyqtSlot(str, int)
    def _on_battery_update(self, role: str, pct: int) -> None:
        if role == "power_meter":
            self._battery.set_level(pct)
            self._battery_label.setText(f"Bat: {pct} %")

    @pyqtSlot(str, str)
    def _on_connected(self, _mac: str, role: str) -> None:
        if role == "power_meter":
            self._status_label.setText("✅ Connected – pedal to activate")
            self._status_label.setStyleSheet(f"color: {ACCENT_GREEN};")
            self._cal_btn.setEnabled(True)

    @pyqtSlot(str, str)
    def _on_disconnected(self, _mac: str, role: str) -> None:
        if role == "power_meter":
            self._status_label.setText("Disconnected")
            self._status_label.setStyleSheet(f"color: {ACCENT_RED};")
            self._cal_btn.setEnabled(False)
            self._power_display.reset()
            self._zone.reset()
            self._pedal_label.setVisible(True)

    @pyqtSlot()
    def _start_calibration(self) -> None:
        mac = self._combo.currentData()
        if mac:
            self._calibration.start_calibration(mac)

    @pyqtSlot(bool, float)
    def _on_calibration_done(self, success: bool, offset: float) -> None:
        if success:
            self._status_label.setText(
                f"✅ Calibrated – offset {offset:.3f} W"
            )
            self._status_label.setStyleSheet(f"color: {ACCENT_GREEN};")
        else:
            self._status_label.setStyleSheet(f"color: {ACCENT_RED};")


class _TrainerPanel(_SensorPanel):
    """Right panel – Elite Real Turbo Muin+ trainer."""

    def __init__(
        self,
        scanner: BLEScanner,
        device_manager: DeviceManager,
        trainer_control: TrainerControl,
        config_manager: ConfigManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__("🚲  Smart Trainer", parent)
        self._scanner = scanner
        self._dm = device_manager
        self._trainer = trainer_control
        self._config = config_manager
        self._devices: dict[str, DeviceInfo] = {}
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        self._scan_btn = ScanButton()
        self._root_layout.addWidget(self._scan_btn)

        self._combo = QComboBox()
        self._combo.addItem("-- Select device --", None)
        self._combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._root_layout.addWidget(self._combo)

        # Note: trainer has no battery info per spec
        rssi_row = QHBoxLayout()
        self._rssi_bar = RSSIBar()
        self._rssi_label = QLabel("RSSI: -- dBm")
        self._rssi_label.setObjectName("statusLabel")
        rssi_row.addWidget(self._rssi_bar)
        rssi_row.addWidget(self._rssi_label)
        rssi_row.addStretch()
        self._root_layout.addLayout(rssi_row)

        # Live data displays
        data_row = QHBoxLayout()
        self._speed_display = MetricDisplay("Speed", "km/h")
        self._cadence_display = MetricDisplay("Cadence", "RPM")
        self._trainer_power_display = MetricDisplay("Power", "W")
        for w in (self._speed_display, self._cadence_display, self._trainer_power_display):
            data_row.addWidget(w)
        self._root_layout.addLayout(data_row)

        # ERG mode controls
        erg_group = QGroupBox("ERG Mode – Target Power")
        erg_layout = QVBoxLayout(erg_group)
        self._power_slider = PowerSlider(minimum=0, maximum=500)
        self._apply_btn = QPushButton("Apply")
        self._apply_btn.setEnabled(False)
        self._apply_btn.setObjectName("successButton")
        erg_layout.addWidget(self._power_slider)
        erg_layout.addWidget(self._apply_btn)
        self._root_layout.addWidget(erg_group)

        # Simulation mode controls
        sim_group = QGroupBox("Simulation Mode – Grade")
        sim_layout = QHBoxLayout(sim_group)
        sim_layout.addWidget(QLabel("Grade (%):"))
        self._grade_slider = QSlider(Qt.Horizontal)
        self._grade_slider.setMinimum(-10)
        self._grade_slider.setMaximum(20)
        self._grade_slider.setValue(0)
        self._grade_label = QLabel("0 %")
        self._grade_label.setFixedWidth(40)
        self._sim_btn = QPushButton("Set Grade")
        self._sim_btn.setEnabled(False)
        sim_layout.addWidget(self._grade_slider)
        sim_layout.addWidget(self._grade_label)
        sim_layout.addWidget(self._sim_btn)
        self._root_layout.addWidget(sim_group)

        self._status_label = QLabel("Not connected")
        self._status_label.setObjectName("statusLabel")
        self._root_layout.addWidget(self._status_label)

        self._root_layout.addStretch()

    def _connect_signals(self) -> None:
        self._scan_btn.scan_requested.connect(self._start_scan)
        self._scan_btn.stop_requested.connect(self._stop_scan)
        self._combo.currentIndexChanged.connect(self._on_device_selected)
        self._apply_btn.clicked.connect(self._apply_erg)
        self._sim_btn.clicked.connect(self._apply_simulation)
        self._grade_slider.valueChanged.connect(
            lambda v: self._grade_label.setText(f"{v} %")
        )

        self._scanner.device_discovered.connect(self._on_device_found)
        self._scanner.scan_complete.connect(lambda: self._scan_btn.set_scanning(False))

        self._trainer.connected.connect(self._on_connected)
        self._trainer.disconnected.connect(self._on_disconnected)
        self._trainer.data_updated.connect(self._on_data_update)
        self._trainer.error.connect(
            lambda msg: self._status_label.setText(f"⚠ {msg}")
        )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _start_scan(self) -> None:
        self._devices.clear()
        self._combo.clear()
        self._combo.addItem("-- Select device --", None)
        self._scanner.start_scan()
        self._scan_btn.set_scanning(True)

    @pyqtSlot()
    def _stop_scan(self) -> None:
        self._scanner.stop_scan()
        self._scan_btn.set_scanning(False)

    @pyqtSlot(object)
    def _on_device_found(self, info: DeviceInfo) -> None:
        if not info.is_fitness_machine:
            return
        self._devices[info.address] = info
        label = f"{info.name} ({info.address})  [{info.rssi} dBm]"
        for i in range(1, self._combo.count()):
            if self._combo.itemData(i) == info.address:
                self._combo.setItemText(i, label)
                return
        self._combo.addItem(label, info.address)

    @pyqtSlot(int)
    def _on_device_selected(self, index: int) -> None:
        mac = self._combo.itemData(index)
        if mac:
            self._trainer.connect_trainer(mac)
            self._config.set_sensor_mac("trainer", mac)
            if mac in self._devices:
                info = self._devices[mac]
                self._rssi_bar.set_rssi(info.rssi)
                self._rssi_label.setText(f"RSSI: {info.rssi} dBm")

    @pyqtSlot(object)
    def _on_data_update(self, data: BikeData) -> None:
        self._speed_display.set_value(data.speed_kmh, fmt="{:.1f}")
        self._cadence_display.set_value(int(data.cadence_rpm))
        self._trainer_power_display.set_value(data.power_w)

    @pyqtSlot()
    def _on_connected(self) -> None:
        self._status_label.setText("✅ Connected")
        self._status_label.setStyleSheet(f"color: {ACCENT_GREEN};")
        self._apply_btn.setEnabled(True)
        self._sim_btn.setEnabled(True)

    @pyqtSlot()
    def _on_disconnected(self) -> None:
        self._status_label.setText("Disconnected")
        self._status_label.setStyleSheet(f"color: {ACCENT_RED};")
        self._apply_btn.setEnabled(False)
        self._sim_btn.setEnabled(False)
        for disp in (self._speed_display, self._cadence_display, self._trainer_power_display):
            disp.reset()

    @pyqtSlot()
    def _apply_erg(self) -> None:
        self._trainer.set_target_power(self._power_slider.value)
        self._status_label.setText(f"ERG: {self._power_slider.value} W")

    @pyqtSlot()
    def _apply_simulation(self) -> None:
        grade = self._grade_slider.value()
        self._trainer.set_simulation(grade=float(grade))
        self._status_label.setText(f"Simulation: {grade} % grade")


class MainWindow(QMainWindow):
    """Application main window.

    Creates and wires together the three sensor panels, the shared BLE
    scanner, device manager, trainer control, and calculator.  A 1-second
    QTimer drives the :class:`DataCalculator` tick for session stats.

    Args:
        config_manager: Loaded configuration manager.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config_manager

        # Core components
        self._calculator = DataCalculator()
        self._device_manager = DeviceManager(self)
        self._trainer_control = TrainerControl(self)
        self._calibration = PowerMeterCalibration(config_manager, self)

        # Separate scanners per panel (each runs its own timed scan)
        self._hr_scanner = BLEScanner(scan_duration=15.0)
        self._power_scanner = BLEScanner(scan_duration=15.0)
        self._trainer_scanner = BLEScanner(scan_duration=15.0)

        self._setup_ui()
        self._apply_stylesheet()
        self._start_session_timer()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle("Cardio Trainer")
        self.setMinimumSize(960, 640)
        self.resize(1200, 700)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Left panel – HR
        self._hr_panel = _HRPanel(
            scanner=self._hr_scanner,
            device_manager=self._device_manager,
            config_manager=self._config,
            calculator=self._calculator,
        )
        main_layout.addWidget(self._hr_panel, stretch=1)

        # Centre panel – Power meter
        self._power_panel = _PowerPanel(
            scanner=self._power_scanner,
            device_manager=self._device_manager,
            config_manager=self._config,
            calibration=self._calibration,
            calculator=self._calculator,
        )
        main_layout.addWidget(self._power_panel, stretch=1)

        # Right panel – Trainer
        self._trainer_panel = _TrainerPanel(
            scanner=self._trainer_scanner,
            device_manager=self._device_manager,
            trainer_control=self._trainer_control,
            config_manager=self._config,
        )
        main_layout.addWidget(self._trainer_panel, stretch=1)

        # Status bar
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("Ready – scan for BLE devices to begin")

    def _apply_stylesheet(self) -> None:
        QApplication.instance().setStyleSheet(APP_STYLESHEET)

    def _start_session_timer(self) -> None:
        self._session_timer = QTimer(self)
        self._session_timer.timeout.connect(self._tick)
        self._session_timer.start(1000)

    # ------------------------------------------------------------------
    # Slots / overrides
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _tick(self) -> None:
        self._calculator.tick(1.0)
        tss = self._calculator.tss()
        np = self._calculator.normalised_power()
        self.statusBar().showMessage(
            f"NP: {np} W  |  TSS: {tss:.1f}  |  "
            f"Calories: {self._calculator.calories_burned():.0f} kcal"
        )

    def closeEvent(self, event) -> None:  # noqa: D401
        """Clean up connections before closing."""
        self._session_timer.stop()
        self._device_manager.disconnect_all()
        self._trainer_control.disconnect_trainer()
        super().closeEvent(event)
