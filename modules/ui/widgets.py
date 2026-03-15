"""
Custom Widgets

Reusable PyQt5 widget components for the cardio-trainer application:
  - MetricDisplay  – large numeric readout with label and unit
  - BatteryIndicator – segmented battery level indicator
  - RSSIBar        – signal-strength bar display
  - ZoneIndicator  – colour-coded zone badge
  - ScanButton     – animated scan / stop button
  - PowerSlider    – labelled slider for target-power control
"""

import logging
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from modules.ui.styles import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_ORANGE,
    ACCENT_RED,
    BACKGROUND_CARD,
    BACKGROUND_DARK,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    zone_color,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MetricDisplay
# ---------------------------------------------------------------------------

class MetricDisplay(QFrame):
    """Large numeric readout widget used for HR, power, cadence, etc.

    Args:
        label: Metric name shown above the value (e.g. ``"Heart Rate"``).
        unit: Unit text shown below the value (e.g. ``"BPM"``).
        parent: Optional parent widget.

    Example::

        display = MetricDisplay("Heart Rate", "BPM")
        display.set_value(142)
    """

    def __init__(
        self,
        label: str,
        unit: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("sensorPanel")
        self._setup_ui(label, unit)

    def _setup_ui(self, label: str, unit: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        self._label = QLabel(label.upper())
        self._label.setObjectName("statusLabel")
        self._label.setAlignment(Qt.AlignCenter)

        self._value_label = QLabel("---")
        self._value_label.setObjectName("metricValue")
        self._value_label.setAlignment(Qt.AlignCenter)
        self._value_label.setFont(QFont("Segoe UI", 42, QFont.Bold))

        self._unit_label = QLabel(unit)
        self._unit_label.setObjectName("metricUnit")
        self._unit_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._label)
        layout.addWidget(self._value_label)
        layout.addWidget(self._unit_label)

    def set_value(self, value: int | float, fmt: str = "{}") -> None:
        """Update the displayed value.

        Args:
            value: Numeric value to display.
            fmt: Python format string (default: ``"{}"``).
        """
        self._value_label.setText(fmt.format(value))

    def set_color(self, hex_color: str) -> None:
        """Update the value label colour.

        Args:
            hex_color: CSS colour string (e.g. ``"#e63946"``).
        """
        self._value_label.setStyleSheet(f"color: {hex_color};")

    def reset(self) -> None:
        """Reset display to ``---``."""
        self._value_label.setText("---")
        self._value_label.setStyleSheet("")


# ---------------------------------------------------------------------------
# BatteryIndicator
# ---------------------------------------------------------------------------

class BatteryIndicator(QWidget):
    """Segmented battery level indicator widget.

    Draws a classic battery icon divided into 5 segments.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._level: int = -1  # -1 = unknown
        self.setFixedSize(42, 20)
        self.setToolTip("Battery level unknown")

    def set_level(self, percent: int) -> None:
        """Set the battery level.

        Args:
            percent: Battery level 0–100.  Pass ``-1`` for unknown.
        """
        self._level = max(-1, min(100, int(percent)))
        tip = f"Battery: {self._level} %" if self._level >= 0 else "Battery level unknown"
        self.setToolTip(tip)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: D401
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        tip_w = 4
        body_w = w - tip_w - 2
        body_h = h - 4

        # Body outline
        painter.setPen(QPen(QColor(TEXT_SECONDARY), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(1, 2, body_w, body_h, 2, 2)

        # Tip
        painter.drawRect(body_w + 2, h // 2 - 3, tip_w - 1, 6)

        if self._level < 0:
            return

        # Fill segments
        num_segments = 5
        seg_w = (body_w - 4) // num_segments
        filled = round(self._level / 100 * num_segments)
        color = (
            QColor(ACCENT_GREEN) if self._level > 30
            else QColor(ACCENT_ORANGE) if self._level > 15
            else QColor(ACCENT_RED)
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        for i in range(filled):
            x = 3 + i * (seg_w + 1)
            painter.drawRect(x, 4, seg_w, body_h - 4)


# ---------------------------------------------------------------------------
# RSSIBar
# ---------------------------------------------------------------------------

class RSSIBar(QWidget):
    """Signal-strength bar display similar to a mobile phone antenna icon.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._rssi: int = -127
        self.setFixedSize(24, 20)
        self.setToolTip("Signal: unknown")

    def set_rssi(self, rssi: int) -> None:
        """Update the RSSI value.

        Args:
            rssi: Signal strength in dBm (typically −127 to 0).
        """
        self._rssi = rssi
        self.setToolTip(f"Signal: {rssi} dBm")
        self.update()

    def _bars(self) -> int:
        if self._rssi >= -55:
            return 4
        if self._rssi >= -65:
            return 3
        if self._rssi >= -75:
            return 2
        if self._rssi >= -85:
            return 1
        return 0

    def paintEvent(self, _event) -> None:  # noqa: D401
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        num_bars = 4
        bar_w = (w - num_bars) // num_bars
        filled = self._bars()

        for i in range(num_bars):
            bar_h = int(h * (i + 1) / num_bars)
            x = i * (bar_w + 1)
            y = h - bar_h
            color = QColor(ACCENT_BLUE) if i < filled else QColor(TEXT_MUTED)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(x, y, bar_w, bar_h, 1, 1)


# ---------------------------------------------------------------------------
# ZoneIndicator
# ---------------------------------------------------------------------------

class ZoneIndicator(QLabel):
    """Colour-coded zone badge label.

    Args:
        zone_type: ``"power"`` or ``"hr"``.
        parent: Optional parent widget.
    """

    def __init__(self, zone_type: str = "power", parent: Optional[QWidget] = None) -> None:
        super().__init__("Zone --", parent)
        self._zone_type = zone_type
        self.setAlignment(Qt.AlignCenter)
        self._apply_style("#4a5568")

    def set_zone(self, zone_number: int, zone_name: str) -> None:
        """Update the displayed zone.

        Args:
            zone_number: 1-indexed zone number.
            zone_name: Human-readable zone label.
        """
        color = zone_color(zone_number, self._zone_type)
        self.setText(f"Zone {zone_number}")
        self.setToolTip(zone_name)
        self._apply_style(color)

    def _apply_style(self, bg_color: str) -> None:
        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {bg_color};
                color: {BACKGROUND_DARK};
                border-radius: 10px;
                padding: 2px 10px;
                font-weight: bold;
                font-size: 11px;
            }}
            """
        )

    def reset(self) -> None:
        """Reset to unknown zone state."""
        self.setText("Zone --")
        self._apply_style("#4a5568")


# ---------------------------------------------------------------------------
# ScanButton
# ---------------------------------------------------------------------------

class ScanButton(QPushButton):
    """Button that alternates between 'Scan' and 'Stop Scanning' states.

    Signals:
        scan_requested: Emitted when the user clicks to start scanning.
        stop_requested: Emitted when the user clicks to stop scanning.
    """

    scan_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("🔍  Scan for Devices", parent)
        self._scanning = False
        self.clicked.connect(self._handle_click)

    def _handle_click(self) -> None:
        if self._scanning:
            self.stop_requested.emit()
        else:
            self.scan_requested.emit()

    def set_scanning(self, scanning: bool) -> None:
        """Update the button state.

        Args:
            scanning: ``True`` while a BLE scan is active.
        """
        self._scanning = scanning
        if scanning:
            self.setText("⏹  Stop Scanning")
            self.setObjectName("dangerButton")
        else:
            self.setText("🔍  Scan for Devices")
            self.setObjectName("")
        self.style().unpolish(self)
        self.style().polish(self)


# ---------------------------------------------------------------------------
# PowerSlider
# ---------------------------------------------------------------------------

class PowerSlider(QWidget):
    """Labelled horizontal slider for setting target power.

    Signals:
        value_changed: Emitted with the new power value (watts) when the
            slider is moved.
    """

    value_changed = pyqtSignal(int)

    def __init__(
        self,
        minimum: int = 0,
        maximum: int = 500,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._setup_ui(minimum, maximum)

    def _setup_ui(self, minimum: int, maximum: int) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Target Power:")
        label.setStyleSheet(f"color: {TEXT_SECONDARY};")

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(minimum)
        self._slider.setMaximum(maximum)
        self._slider.setValue(0)
        self._slider.setTickInterval(50)
        self._slider.setTickPosition(QSlider.TicksBelow)
        self._slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._spinbox = QSpinBox()
        self._spinbox.setMinimum(minimum)
        self._spinbox.setMaximum(maximum)
        self._spinbox.setSuffix(" W")
        self._spinbox.setFixedWidth(80)

        self._slider.valueChanged.connect(self._spinbox.setValue)
        self._spinbox.valueChanged.connect(self._slider.setValue)
        self._slider.valueChanged.connect(self.value_changed)

        layout.addWidget(label)
        layout.addWidget(self._slider)
        layout.addWidget(self._spinbox)

    @property
    def value(self) -> int:
        """Current slider value in watts."""
        return self._slider.value()

    def set_value(self, watts: int) -> None:
        """Set the slider position programmatically.

        Args:
            watts: Target power in watts.
        """
        self._slider.setValue(watts)
