# Cardio Trainer

A PC-based cycling training application for managing and displaying real-time data from BLE fitness sensors.

## Features

- **Heart Rate Monitoring** – live BPM display with zone classification (Polar H10 and other HR sensors)
- **Power Meter** – real-time power, W/kg, normalised power, and zone display (Stages, Quarq, etc.)
- **Smart Trainer Control** – ERG mode (target power) and simulation mode (road gradient) via FTMS protocol (Elite Real Turbo Muin+)
- **BLE Device Discovery** – automatic scanning with RSSI and battery level indicators
- **Calibration** – zero-offset calibration for strain-gauge power meters
- **Session Statistics** – TSS, IF, NP, and calorie estimation updated every second
- **Persistent Configuration** – last-used device MAC addresses saved across sessions

## Project Structure

```
cardio-trainer/
├── modules/
│   ├── connection/
│   │   ├── ble_scanner.py       # BLE device scanning
│   │   └── device_manager.py    # Device connection management
│   ├── logic/
│   │   ├── calculations.py      # Calculations and conversions
│   │   └── calibration.py       # Power meter calibration
│   ├── ui/
│   │   ├── main_window.py       # Main PyQt5 window (3-panel layout)
│   │   ├── widgets.py           # Custom widgets
│   │   └── styles.py            # UI styling
│   └── trainer/
│       └── control.py           # Elite Muin+ FTMS control
├── config/
│   ├── sensors.json             # Sensor configuration (auto-generated)
│   └── config_manager.py        # Configuration file handling
├── main.py                      # Application entry point
└── requirements.txt
```

## Requirements

- Python 3.11+
- A Bluetooth 4.0+ adapter

## Installation

```bash
# Clone the repository
git clone https://github.com/seradamus-pixel/cardio-trainer.git
cd cardio-trainer

# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
.venv\Scripts\activate             # Windows

# Install dependencies
pip install -r requirements.txt
```

## Running the Application

```bash
python main.py
```

Optional flags:

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--log-level` | DEBUG, INFO, WARNING, ERROR | INFO | Logging verbosity |

Example:

```bash
python main.py --log-level DEBUG
```

## Usage

1. **Heart Rate Sensor (left panel)**
   - Click **Scan for Devices** to discover nearby BLE HR monitors.
   - Select your Polar H10 (or compatible sensor) from the drop-down.
   - The live BPM readout and heart rate zone will update automatically.
   - Click **Continue →** once connected to proceed.

2. **Power Meter (centre panel)**
   - Click **Scan for Devices** and select your power meter.
   - Start pedalling – the power display will activate automatically.
   - Use **Calibrate Zero Offset** to perform a static zero calibration.

3. **Smart Trainer (right panel)**
   - Scan and select your Elite Real Turbo Muin+ (or other FTMS trainer).
   - Use the **ERG Mode** slider to set a target power and click **Apply**.
   - Use the **Simulation Mode** slider to set a virtual road gradient.

## Supported Devices

| Role | Protocol | Examples |
|------|----------|---------|
| Heart Rate | BLE HRS (0x180D) | Polar H10, Garmin HRM-Pro |
| Power Meter | BLE CPS (0x1818) | Stages, Quarq, Garmin Vector |
| Smart Trainer | FTMS (0x1826) | Elite Real Turbo Muin+, Wahoo KICKR |

## Configuration

Sensor MAC addresses are stored in `config/sensors.json` and loaded automatically on next launch.

```json
{
  "sensors": {
    "heart_rate": { "mac_address": "AA:BB:CC:DD:EE:FF", ... },
    "power_meter": { "mac_address": "...", ... },
    "trainer":     { "mac_address": "...", ... }
  },
  "calibration": {
    "power_offset": 0.0,
    "last_calibrated": "2025-01-01T10:00:00"
  }
}
```

## License

MIT
