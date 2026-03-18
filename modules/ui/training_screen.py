"""
Training Screen

Large-format training interface widget for live cycling sessions.

Layout (top → bottom)
----------------------

  ┌─────────────────────┬─────────────────────────────────┐
  │  Status panel        │      Digital clock               │
  │  Pulsometr  ✓  🔋   │       00:00:00                   │
  │  Trenażer   ✓  🔋   │                                  │
  ├──────────┬───────────┴──────────────────────────────────┤
  │          │                                               │
  │   BPM    │      W           │       RPM                 │
  │   ---    │      ---         │        ---                │
  │          │                  │                           │
  ├──────────┴──────────────────┴───────────────────────────┤
  │  Power control              │   HR Drift                │
  │  Target: [ 200 ] W  80 %FTP │   Drift:  +1.2 BPM/min   │
  │  Mode: ERG                  │   Initial HR: 142 BPM     │
  ├─────────────────────────────┴───────────────────────────┤
  │       [▶ Start]  [⏸ Pause]  [↺ Reset]                  │
  └─────────────────────────────────────────────────────────┘
"""

import logging
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from modules.ui.styles import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_ORANGE,
    ACCENT_RED,
    BACKGROUND_DARK,
    BACKGROUND_PANEL,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
)
from modules.ui.widgets import BatteryIndicator, MetricDisplay

logger = logging.getLogger(__name__)

# Large font sizes for the training screen
_FONT_CLOCK = QFont("Courier New", 56, QFont.Bold)
_FONT_METRIC = QFont("Segoe UI", 64, QFont.Bold)
_FONT_LABEL = QFont("Segoe UI", 13)
_FONT_STATUS_TITLE = QFont("Segoe UI", 11, QFont.Bold)

# Cadence threshold for auto-start of the timer
_CADENCE_AUTOSTART_THRESHOLD = 1.0  # RPM


# ---------------------------------------------------------------------------
# _StatusRow
# ---------------------------------------------------------------------------

class _StatusRow(QWidget):
    """One row in the status panel: icon + name + battery + status dot."""

    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        self._dot = QLabel("●")
        self._dot.setFixedWidth(14)
        self._dot.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px;")

        self._name_lbl = QLabel(label)
        self._name_lbl.setFont(_FONT_LABEL)
        self._name_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        self._name_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self._battery = BatteryIndicator()

        self._rssi_lbl = QLabel("")
        self._rssi_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px;")
        self._rssi_lbl.setFixedWidth(58)

        layout.addWidget(self._dot)
        layout.addWidget(self._name_lbl)
        layout.addWidget(self._battery)
        layout.addWidget(self._rssi_lbl)

    def set_connected(self, connected: bool) -> None:
        color = ACCENT_GREEN if connected else TEXT_MUTED
        self._dot.setStyleSheet(f"color: {color}; font-size: 14px;")

    def set_battery(self, percent: int) -> None:
        self._battery.set_level(percent)

    def set_rssi(self, rssi: int) -> None:
        self._rssi_lbl.setText(f"{rssi} dBm")


# ---------------------------------------------------------------------------
# _StatusPanel
# ---------------------------------------------------------------------------

class _StatusPanel(QGroupBox):
    """Top-left panel showing connected sensor status and battery levels."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Czujniki / Sensors", parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 12, 8, 8)

        self._hr_row = _StatusRow("Pulsometr (HR)", self)
        self._trainer_row = _StatusRow("Trenażer", self)

        layout.addWidget(self._hr_row)
        layout.addWidget(self._trainer_row)
        layout.addStretch()

    def set_hr_connected(self, connected: bool) -> None:
        self._hr_row.set_connected(connected)

    def set_trainer_connected(self, connected: bool) -> None:
        self._trainer_row.set_connected(connected)

    def set_hr_battery(self, percent: int) -> None:
        self._hr_row.set_battery(percent)

    def set_trainer_battery(self, percent: int) -> None:
        self._trainer_row.set_battery(percent)

    def set_hr_rssi(self, rssi: int) -> None:
        self._hr_row.set_rssi(rssi)

    def set_trainer_rssi(self, rssi: int) -> None:
        self._trainer_row.set_rssi(rssi)


# ---------------------------------------------------------------------------
# _ClockWidget
# ---------------------------------------------------------------------------

class _ClockWidget(QWidget):
    """Large digital elapsed-time display (HH:MM:SS)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(8, 4, 8, 4)

        title = QLabel("CZAS TRENINGU")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: bold; letter-spacing: 2px;"
        )

        self._time_lbl = QLabel("00:00:00")
        self._time_lbl.setFont(_FONT_CLOCK)
        self._time_lbl.setAlignment(Qt.AlignCenter)
        self._time_lbl.setStyleSheet(f"color: {ACCENT_BLUE};")

        layout.addWidget(title)
        layout.addWidget(self._time_lbl)

    def set_elapsed(self, total_seconds: int) -> None:
        """Update the display.

        Args:
            total_seconds: Elapsed time in whole seconds.
        """
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        self._time_lbl.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def set_running(self, running: bool) -> None:
        """Toggle colour to indicate whether the clock is ticking."""
        color = ACCENT_BLUE if running else TEXT_SECONDARY
        self._time_lbl.setStyleSheet(f"color: {color};")


# ---------------------------------------------------------------------------
# _PowerControlPanel
# ---------------------------------------------------------------------------

class _PowerControlPanel(QGroupBox):
    """Bottom-left panel: set target power in watts and see %FTP."""

    def __init__(self, ftp: int = 250, parent: Optional[QWidget] = None) -> None:
        super().__init__("Sterowanie mocą / Power Control", parent)
        self._ftp = max(1, ftp)
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 14, 10, 10)
        outer.setSpacing(8)

        # ── Target watts row ──────────────────────────────────────────
        watts_row = QHBoxLayout()
        lbl = QLabel("Cel / Target:")
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        lbl.setFixedWidth(100)

        self._watts_spin = QSpinBox()
        self._watts_spin.setRange(0, 2000)
        self._watts_spin.setSuffix("  W")
        self._watts_spin.setFont(QFont("Segoe UI", 22, QFont.Bold))
        self._watts_spin.setFixedHeight(50)
        self._watts_spin.setAlignment(Qt.AlignCenter)
        self._watts_spin.valueChanged.connect(self._on_watts_changed)

        watts_row.addWidget(lbl)
        watts_row.addWidget(self._watts_spin)

        # ── %FTP row ──────────────────────────────────────────────────
        ftp_row = QHBoxLayout()
        ftp_lbl = QLabel("FTP %:")
        ftp_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        ftp_lbl.setFixedWidth(100)

        self._ftp_lbl = QLabel("0 %")
        self._ftp_lbl.setFont(QFont("Segoe UI", 22, QFont.Bold))
        self._ftp_lbl.setStyleSheet(f"color: {ACCENT_ORANGE};")
        self._ftp_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        ftp_row.addWidget(ftp_lbl)
        ftp_row.addWidget(self._ftp_lbl)

        # ── Mode row ──────────────────────────────────────────────────
        mode_row = QHBoxLayout()
        mode_static = QLabel("Tryb / Mode:")
        mode_static.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        mode_static.setFixedWidth(100)

        self._mode_lbl = QLabel("ERG")
        self._mode_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self._mode_lbl.setStyleSheet(f"color: {ACCENT_GREEN};")

        mode_row.addWidget(mode_static)
        mode_row.addWidget(self._mode_lbl)

        # ── Apply button ──────────────────────────────────────────────
        self._apply_btn = QPushButton("⚡  Zastosuj / Apply")
        self._apply_btn.setObjectName("successButton")
        self._apply_btn.setFixedHeight(38)

        outer.addLayout(watts_row)
        outer.addLayout(ftp_row)
        outer.addLayout(mode_row)
        outer.addWidget(self._apply_btn)
        outer.addStretch()

    # ------------------------------------------------------------------
    # Signals (forwarded via button)
    # ------------------------------------------------------------------

    @property
    def apply_button(self) -> QPushButton:
        return self._apply_btn

    @property
    def watts_spinbox(self) -> QSpinBox:
        return self._watts_spin

    # ------------------------------------------------------------------
    # Update methods
    # ------------------------------------------------------------------

    def set_target_watts(self, watts: int) -> None:
        self._watts_spin.blockSignals(True)
        self._watts_spin.setValue(watts)
        self._watts_spin.blockSignals(False)
        self._update_ftp_display(watts)

    def set_mode_label(self, mode_text: str, is_erg: bool = True) -> None:
        self._mode_lbl.setText(mode_text)
        color = ACCENT_GREEN if is_erg else ACCENT_ORANGE
        self._mode_lbl.setStyleSheet(f"color: {color};")

    def set_ftp(self, ftp: int) -> None:
        self._ftp = max(1, ftp)
        self._update_ftp_display(self._watts_spin.value())

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_watts_changed(self, watts: int) -> None:
        self._update_ftp_display(watts)

    def _update_ftp_display(self, watts: int) -> None:
        pct = round(watts / self._ftp * 100)
        self._ftp_lbl.setText(f"{pct} %")
        if pct >= 100:
            color = ACCENT_RED
        elif pct >= 75:
            color = ACCENT_ORANGE
        else:
            color = ACCENT_BLUE
        self._ftp_lbl.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold;")


# ---------------------------------------------------------------------------
# _HRDriftPanel
# ---------------------------------------------------------------------------

class _HRDriftPanel(QGroupBox):
    """Bottom-right panel: heart-rate drift computation."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Dryf tętna / HR Drift", parent)
        self._initial_hr: Optional[int] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(8)

        def _row(static_text: str, value_text: str, value_color: str) -> tuple:
            row = QHBoxLayout()
            slbl = QLabel(static_text)
            slbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
            slbl.setFixedWidth(130)
            vlbl = QLabel(value_text)
            vlbl.setFont(QFont("Segoe UI", 20, QFont.Bold))
            vlbl.setStyleSheet(f"color: {value_color}; font-size: 20px; font-weight: bold;")
            row.addWidget(slbl)
            row.addWidget(vlbl)
            return row, vlbl

        drift_row, self._drift_lbl = _row("Dryf / Drift:", "--- BPM/min", ACCENT_ORANGE)
        init_row, self._init_hr_lbl = _row("Początkowe HR:", "--- BPM", TEXT_SECONDARY)
        curr_row, self._curr_hr_lbl = _row("Aktualne HR:", "--- BPM", ACCENT_BLUE)

        layout.addLayout(drift_row)
        layout.addLayout(init_row)
        layout.addLayout(curr_row)
        layout.addStretch()

    # ------------------------------------------------------------------
    # Update methods
    # ------------------------------------------------------------------

    def update_hr_drift(
        self,
        current_hr: int,
        initial_hr: int,
        elapsed_minutes: float,
    ) -> None:
        """Recompute and display the HR drift.

        Args:
            current_hr: Most recent HR reading (BPM).
            initial_hr: HR at the start of the session (BPM).
            elapsed_minutes: Session duration in minutes.
        """
        self._curr_hr_lbl.setText(f"{current_hr} BPM")
        self._init_hr_lbl.setText(f"{initial_hr} BPM")

        if elapsed_minutes >= 1.0 and initial_hr > 0:
            drift = (current_hr - initial_hr) / elapsed_minutes
            sign = "+" if drift >= 0 else ""
            self._drift_lbl.setText(f"{sign}{drift:.1f} BPM/min")
            color = ACCENT_RED if drift > 2 else (ACCENT_ORANGE if drift > 0 else ACCENT_GREEN)
            self._drift_lbl.setStyleSheet(
                f"color: {color}; font-size: 20px; font-weight: bold;"
            )
        else:
            self._drift_lbl.setText("--- BPM/min")

    def reset(self) -> None:
        self._drift_lbl.setText("--- BPM/min")
        self._init_hr_lbl.setText("--- BPM")
        self._curr_hr_lbl.setText("--- BPM")
        self._drift_lbl.setStyleSheet(
            f"color: {ACCENT_ORANGE}; font-size: 20px; font-weight: bold;"
        )


# ---------------------------------------------------------------------------
# TrainingScreen
# ---------------------------------------------------------------------------

class TrainingScreen(QWidget):
    """Main large-display training interface.

    This widget is designed to be used as the central widget of a
    :class:`~modules.trainer_ui.TrainerUI` window.  It exposes
    update slots that are connected to BLE client signals and a 1-second
    QTimer for the elapsed-time display.

    Args:
        ftp: Athlete FTP in watts (for %FTP display).
        parent: Optional parent widget.

    Signals exposed via child widgets (connect via :attr:`apply_button`):
        apply_button.clicked: User clicked "Apply" in the power panel.

    Example::

        screen = TrainingScreen(ftp=250)
        ble_client.hr_updated.connect(screen.update_hr)
        ble_client.power_updated.connect(screen.update_power)
        ble_client.cadence_updated.connect(screen.update_cadence)
        screen.apply_button.clicked.connect(my_apply_handler)
    """

    def __init__(self, ftp: int = 250, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._ftp = max(1, ftp)
        self._elapsed_seconds: int = 0
        self._timer_running: bool = False
        self._initial_hr: int = 0
        self._current_hr: int = 0
        self._current_cadence: float = 0.0

        self._setup_ui()
        self._setup_timer()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ── Row 0: Status + Clock ─────────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self._status_panel = _StatusPanel(self)
        self._status_panel.setMinimumWidth(260)
        self._status_panel.setMaximumWidth(320)

        self._clock = _ClockWidget(self)
        self._clock.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        top_row.addWidget(self._status_panel)
        top_row.addWidget(self._clock, stretch=1)

        # ── Row 1: Three metric cards ─────────────────────────────────
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(10)

        self._hr_display = MetricDisplay("Tętno / Heart Rate", "BPM", self)
        self._power_display = MetricDisplay("Moc / Power", "W", self)
        self._cadence_display = MetricDisplay("Kadencja / Cadence", "RPM", self)

        for disp in (self._hr_display, self._power_display, self._cadence_display):
            disp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            disp._value_label.setFont(_FONT_METRIC)
            metrics_row.addWidget(disp, stretch=1)

        # ── Row 2: Power control + HR drift ───────────────────────────
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        self._power_panel = _PowerControlPanel(ftp=self._ftp, parent=self)
        self._power_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self._drift_panel = _HRDriftPanel(self)
        self._drift_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        bottom_row.addWidget(self._power_panel, stretch=1)
        bottom_row.addWidget(self._drift_panel, stretch=1)

        # ── Row 3: Timer buttons ──────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self._start_btn = QPushButton("▶  Start")
        self._start_btn.setObjectName("successButton")
        self._start_btn.setFixedHeight(40)
        self._start_btn.clicked.connect(self._on_start_clicked)

        self._pause_btn = QPushButton("⏸  Pauza")
        self._pause_btn.setFixedHeight(40)
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._on_pause_clicked)

        self._reset_btn = QPushButton("↺  Reset")
        self._reset_btn.setObjectName("dangerButton")
        self._reset_btn.setFixedHeight(40)
        self._reset_btn.clicked.connect(self._on_reset_clicked)

        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._pause_btn)
        btn_row.addWidget(self._reset_btn)
        btn_row.addStretch()

        # ── Assemble root layout ──────────────────────────────────────
        root.addLayout(top_row)
        root.addLayout(metrics_row, stretch=2)
        root.addLayout(bottom_row)
        root.addLayout(btn_row)

    def _setup_timer(self) -> None:
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def apply_button(self) -> QPushButton:
        """The "Apply" button in the power control panel."""
        return self._power_panel.apply_button

    @property
    def watts_spinbox(self) -> QSpinBox:
        """Spinbox that holds the desired target power."""
        return self._power_panel.watts_spinbox

    @property
    def elapsed_seconds(self) -> int:
        """Total elapsed training time in seconds."""
        return self._elapsed_seconds

    @property
    def current_hr(self) -> int:
        """Most recent heart rate reading in BPM (0 if not yet received)."""
        return self._current_hr

    @property
    def current_power(self) -> int:
        """Most recent power reading in watts (0 if not yet received)."""
        text = self._power_display._value_label.text()
        try:
            return int(text)
        except ValueError:
            return 0

    @property
    def current_cadence(self) -> float:
        """Most recent cadence reading in RPM (0.0 if not yet received)."""
        return self._current_cadence

    # ------------------------------------------------------------------
    # Public update slots
    # ------------------------------------------------------------------

    @pyqtSlot(int)
    def update_hr(self, bpm: int) -> None:
        """Update the heart rate display.

        Args:
            bpm: Heart rate in beats per minute.
        """
        self._current_hr = bpm
        self._hr_display.set_value(bpm)
        if self._initial_hr == 0 and bpm > 0 and self._timer_running:
            self._initial_hr = bpm
        self._refresh_drift()

    @pyqtSlot(int)
    def update_power(self, watts: int) -> None:
        """Update the power display.

        Args:
            watts: Power in watts.
        """
        self._power_display.set_value(watts)

    @pyqtSlot(float)
    def update_cadence(self, rpm: float) -> None:
        """Update the cadence display and auto-start the timer.

        The timer is started automatically when cadence exceeds
        ``_CADENCE_AUTOSTART_THRESHOLD`` RPM and paused when it drops to zero.

        Args:
            rpm: Cadence in revolutions per minute.
        """
        self._current_cadence = rpm
        self._cadence_display.set_value(int(rpm))

        if rpm >= _CADENCE_AUTOSTART_THRESHOLD and not self._timer_running:
            self._start_timer()
        elif rpm < _CADENCE_AUTOSTART_THRESHOLD and self._timer_running:
            self._pause_timer()

    @pyqtSlot(str)
    def on_sensor_connected(self, role: str) -> None:
        """React to a sensor connection event.

        Args:
            role: Device role string (``"heart_rate"`` or ``"trainer"``).
        """
        if role == "heart_rate":
            self._status_panel.set_hr_connected(True)
        elif role in ("trainer", "power_meter"):
            self._status_panel.set_trainer_connected(True)

    @pyqtSlot(str)
    def on_sensor_disconnected(self, role: str) -> None:
        """React to a sensor disconnection event.

        Args:
            role: Device role string.
        """
        if role == "heart_rate":
            self._status_panel.set_hr_connected(False)
        elif role in ("trainer", "power_meter"):
            self._status_panel.set_trainer_connected(False)

    @pyqtSlot(int)
    def on_hr_battery(self, percent: int) -> None:
        self._status_panel.set_hr_battery(percent)

    @pyqtSlot(int)
    def on_trainer_battery(self, percent: int) -> None:
        self._status_panel.set_trainer_battery(percent)

    def set_mode_label(self, mode_text: str, is_erg: bool = True) -> None:
        """Update the mode label in the power panel.

        Args:
            mode_text: Human-readable mode string.
            is_erg: ``True`` for ERG mode (green), ``False`` for Resistance (orange).
        """
        self._power_panel.set_mode_label(mode_text, is_erg)

    def set_ftp(self, ftp: int) -> None:
        """Update the FTP value used for %FTP calculations.

        Args:
            ftp: FTP in watts.
        """
        self._ftp = max(1, ftp)
        self._power_panel.set_ftp(self._ftp)

    # ------------------------------------------------------------------
    # Timer control
    # ------------------------------------------------------------------

    def _start_timer(self) -> None:
        if not self._timer_running:
            self._timer_running = True
            self._tick_timer.start()
            self._clock.set_running(True)
            self._start_btn.setEnabled(False)
            self._pause_btn.setEnabled(True)
            logger.debug("Training timer started")

    def _pause_timer(self) -> None:
        if self._timer_running:
            self._timer_running = False
            self._tick_timer.stop()
            self._clock.set_running(False)
            self._start_btn.setEnabled(True)
            self._pause_btn.setEnabled(False)
            logger.debug("Training timer paused at %d s", self._elapsed_seconds)

    def _on_start_clicked(self) -> None:
        self._start_timer()

    def _on_pause_clicked(self) -> None:
        self._pause_timer()

    def _on_reset_clicked(self) -> None:
        self._pause_timer()
        self._elapsed_seconds = 0
        self._initial_hr = 0
        self._clock.set_elapsed(0)
        self._drift_panel.reset()
        logger.debug("Training timer reset")

    @pyqtSlot()
    def _on_tick(self) -> None:
        self._elapsed_seconds += 1
        self._clock.set_elapsed(self._elapsed_seconds)
        self._refresh_drift()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _refresh_drift(self) -> None:
        if self._current_hr > 0 and self._initial_hr > 0:
            elapsed_min = self._elapsed_seconds / 60.0
            self._drift_panel.update_hr_drift(
                current_hr=self._current_hr,
                initial_hr=self._initial_hr,
                elapsed_minutes=elapsed_min,
            )
