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

### Training Interface (Part 2)

- **Large training display** – full-screen clock, HR / Power / Cadence cards
- **Auto-start timer** – timer starts automatically when cadence > 0 RPM
- **Power control** – set target watts and see %FTP in real time
- **Smart mode switching** – automatic ERG → Resistance when cadence drops below 20 RPM; restores ERG when cadence recovers above 25 RPM
- **HR Drift panel** – live fatigue trend (BPM/min)
- **Session recording** – workout summary saved to `data/workouts/` on close

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
│   │   ├── main_window.py       # Setup window (3-panel layout)
│   │   ├── training_screen.py   # Large-display training interface
│   │   ├── widgets.py           # Custom widgets
│   │   └── styles.py            # UI styling
│   ├── trainer/
│   │   └── control.py           # Elite Muin+ FTMS control
│   ├── ble_client.py            # Unified BLE wrapper (training mode)
│   ├── power_controller.py      # ERG / Resistance mode logic
│   ├── data_recorder.py         # Session data recording & persistence
│   └── trainer_ui.py            # Main training window
├── config/
│   ├── sensors.json             # Sensor + athlete configuration
│   └── config_manager.py        # Configuration file handling
├── data/
│   └── workouts/                # Saved workout JSON files
├── main.py                      # Device setup entry point
├── main_training.py             # Training session entry point
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

### Step 1 – Device Setup

Scan for BLE sensors and save their MAC addresses:

```bash
python main.py
```

Optional flags:

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--log-level` | DEBUG, INFO, WARNING, ERROR | INFO | Logging verbosity |

### Step 2 – Training Session

Launch the live training interface:

```bash
python main_training.py
```

The training window will automatically connect to the sensors configured in Step 1.

## Usage

### Device Setup (`main.py`)

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

### Training Session (`main_training.py`)

- **Status panel (top-left)** – shows connected sensors and battery levels.
- **Digital clock (top-centre)** – auto-starts when you begin pedalling.
- **Metric cards** – large Heart Rate / Power / Cadence displays.
- **Power control (bottom-left)** – type a target watts value and press **Apply**.
  - The trainer will hold that power in ERG mode.
  - If cadence drops below 20 RPM the trainer automatically switches to low
    resistance mode to help you recover.  ERG mode is restored when cadence
    rises above 25 RPM.
- **HR Drift (bottom-right)** – shows (current HR − initial HR) / elapsed minutes.
- **Timer buttons** – manual Start / Pause / Reset in addition to auto-start.
- Closing the window saves the workout summary to `data/workouts/`.

## Athlete Configuration

Edit `config/sensors.json` to set your personal data used for %FTP and HR zone
calculations:

```json
{
  "sensors": { … },
  "calibration": { … },
  "athlete": {
    "ftp": 250,
    "max_hr": 185,
    "weight_kg": 75.0
  }
}
```

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
    "heart_rate": { "mac_address": "AA:BB:CC:DD:EE:FF", … },
    "power_meter": { "mac_address": "…", … },
    "trainer":     { "mac_address": "…", … }
  },
  "calibration": {
    "power_offset": 0.0,
    "last_calibrated": "2025-01-01T10:00:00"
  },
  "athlete": {
    "ftp": 250,
    "max_hr": 185,
    "weight_kg": 75.0
  }
}
```

## License

MIT
