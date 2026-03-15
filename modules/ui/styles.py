"""
UI Styles

Centralised stylesheet and colour definitions for the cardio-trainer
application.  All colours follow a dark athletic theme with clear zone-
colour coding inspired by Garmin/Wahoo conventions.
"""

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
BACKGROUND_DARK = "#1a1a2e"
BACKGROUND_PANEL = "#16213e"
BACKGROUND_CARD = "#0f3460"
ACCENT_BLUE = "#4cc9f0"
ACCENT_GREEN = "#2dc653"
ACCENT_ORANGE = "#f77f00"
ACCENT_RED = "#e63946"
ACCENT_PURPLE = "#7209b7"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#a0aec0"
TEXT_MUTED = "#4a5568"
BORDER_COLOR = "#2d3748"

# HR zone colours (zone 1–5)
HR_ZONE_COLORS = [
    "#4cc9f0",  # Zone 1 – Recovery (blue)
    "#2dc653",  # Zone 2 – Aerobic (green)
    "#f3c623",  # Zone 3 – Tempo (yellow)
    "#f77f00",  # Zone 4 – Threshold (orange)
    "#e63946",  # Zone 5 – VO2max (red)
]

# Power zone colours (zone 1–7)
POWER_ZONE_COLORS = [
    "#a0aec0",  # Zone 1 – Active Recovery (grey)
    "#4cc9f0",  # Zone 2 – Endurance (blue)
    "#2dc653",  # Zone 3 – Tempo (green)
    "#f3c623",  # Zone 4 – Threshold (yellow)
    "#f77f00",  # Zone 5 – VO2max (orange)
    "#e63946",  # Zone 6 – Anaerobic (red)
    "#7209b7",  # Zone 7 – Neuromuscular (purple)
]

# ---------------------------------------------------------------------------
# Global application stylesheet (Qt stylesheet syntax)
# ---------------------------------------------------------------------------
APP_STYLESHEET = f"""
/* ---- Global ---- */
QMainWindow, QWidget {{
    background-color: {BACKGROUND_DARK};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

/* ---- Panels ---- */
QFrame#sensorPanel {{
    background-color: {BACKGROUND_PANEL};
    border: 1px solid {BORDER_COLOR};
    border-radius: 8px;
}}

/* ---- Labels ---- */
QLabel#metricValue {{
    font-size: 48px;
    font-weight: bold;
    color: {ACCENT_BLUE};
}}

QLabel#metricUnit {{
    font-size: 14px;
    color: {TEXT_SECONDARY};
}}

QLabel#sectionTitle {{
    font-size: 15px;
    font-weight: bold;
    color: {ACCENT_BLUE};
    padding-bottom: 4px;
    border-bottom: 1px solid {BORDER_COLOR};
}}

QLabel#statusLabel {{
    font-size: 12px;
    color: {TEXT_SECONDARY};
}}

/* ---- Buttons ---- */
QPushButton {{
    background-color: {ACCENT_BLUE};
    color: {BACKGROUND_DARK};
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: bold;
    font-size: 13px;
}}

QPushButton:hover {{
    background-color: #63d1f4;
}}

QPushButton:pressed {{
    background-color: #38b2db;
}}

QPushButton:disabled {{
    background-color: {TEXT_MUTED};
    color: {TEXT_SECONDARY};
}}

QPushButton#dangerButton {{
    background-color: {ACCENT_RED};
    color: {TEXT_PRIMARY};
}}

QPushButton#dangerButton:hover {{
    background-color: #ff6b6b;
}}

QPushButton#successButton {{
    background-color: {ACCENT_GREEN};
    color: {BACKGROUND_DARK};
}}

/* ---- ComboBox ---- */
QComboBox {{
    background-color: {BACKGROUND_CARD};
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 5px 8px;
    color: {TEXT_PRIMARY};
    min-width: 200px;
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {BACKGROUND_CARD};
    border: 1px solid {BORDER_COLOR};
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_BLUE};
    selection-color: {BACKGROUND_DARK};
}}

/* ---- Spinbox ---- */
QSpinBox, QDoubleSpinBox {{
    background-color: {BACKGROUND_CARD};
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TEXT_PRIMARY};
}}

/* ---- Sliders ---- */
QSlider::groove:horizontal {{
    height: 6px;
    background: {BACKGROUND_CARD};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {ACCENT_BLUE};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}

QSlider::sub-page:horizontal {{
    background: {ACCENT_BLUE};
    border-radius: 3px;
}}

/* ---- Progress bar ---- */
QProgressBar {{
    background-color: {BACKGROUND_CARD};
    border-radius: 4px;
    text-align: center;
    color: {TEXT_PRIMARY};
    height: 10px;
}}

QProgressBar::chunk {{
    background-color: {ACCENT_GREEN};
    border-radius: 4px;
}}

/* ---- Group box ---- */
QGroupBox {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}

/* ---- Scrollbars ---- */
QScrollBar:vertical {{
    background: {BACKGROUND_PANEL};
    width: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {TEXT_MUTED};
    border-radius: 4px;
    min-height: 20px;
}}

/* ---- Status bar ---- */
QStatusBar {{
    background-color: {BACKGROUND_PANEL};
    color: {TEXT_SECONDARY};
    font-size: 11px;
    border-top: 1px solid {BORDER_COLOR};
}}
"""


def zone_color(zone_number: int, zone_type: str = "power") -> str:
    """Return the hex colour for a given zone number.

    Args:
        zone_number: 1-indexed zone number.
        zone_type: ``"power"`` (7 zones) or ``"hr"`` (5 zones).

    Returns:
        Hex colour string such as ``"#2dc653"``.
    """
    if zone_type == "hr":
        colors = HR_ZONE_COLORS
    else:
        colors = POWER_ZONE_COLORS
    idx = max(0, min(zone_number - 1, len(colors) - 1))
    return colors[idx]
