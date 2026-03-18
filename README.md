# Cardio Trainer

A PC-based Bluetooth LE scanner that discovers nearby fitness devices, classifies
them as **Heart Rate Monitors** (pulsometry) or **Trainers** (trenażery), and lets
you manage a saved-device list together with your LTHR and FTP training thresholds.

## Features

- **BLE Device Discovery** – scans for nearby Bluetooth LE devices and shows name,
  MAC address, RSSI, and automatically detected type.
- **Device Classification** – identifies Heart Rate Monitors (BLE HRS 0x180D) and
  Trainers / Power Meters (BLE CPS 0x1818 / FTMS 0x1826) from service UUIDs.
- **Saved Device List** – add or remove devices stored in `config/devices.json`.
- **Training Thresholds** – store and update LTHR (Lactate Threshold Heart Rate) and
  FTP (Functional Threshold Power) in the same config file.
- **Cross-Platform** – runs on Windows, macOS, and Linux wherever Python 3.11+ and
  a Bluetooth 4.0+ adapter are available.
- **Async & Modular** – built with `asyncio` and `bleak`; separate modules for
  scanning, device management, and the UI.

## Project Structure

```
cardio-trainer/
├── modules/
│   ├── ble_scanner.py      # BLE scanning logic (asyncio + bleak)
│   ├── device_manager.py   # Saved devices & config management
│   └── ui.py               # Interactive text UI
├── config/
│   └── devices.json        # Persistent configuration (auto-created)
├── main.py                 # Application entry point
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.11+
- A Bluetooth 4.0+ adapter
- `bleak` ≥ 0.21.0

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
| `--log-level` | DEBUG, INFO, WARNING, ERROR | WARNING | Logging verbosity |
| `--scan-duration` | any positive number | 10 | BLE scan duration in seconds |

Example:

```bash
python main.py --log-level INFO --scan-duration 15
```

## Usage

The application presents a numbered text menu:

```
============================================================
   CARDIO TRAINER – Skaner BLE
============================================================

  Opcje:
  [1] Skanuj urządzenia BLE
  [2] Dodaj urządzenie do listy zapisanych
  [3] Usuń urządzenie z listy zapisanych
  [4] Pokaż zapisane urządzenia
  [5] Ustaw LTHR
  [6] Ustaw FTP
  [7] Pokaż konfigurację
  [0] Wyjście
```

1. **Scan** (option 1) – discovers nearby BLE devices and lists them with RSSI and type.
2. **Add** (option 2) – pick a number from the scanned list to save the device.
3. **Remove** (option 3) – pick a number from the saved list to delete the entry.
4. **LTHR / FTP** (options 5 & 6) – enter your threshold values; they are persisted immediately.

## Configuration File

`config/devices.json` is created automatically on first run:

```json
{
  "devices": [
    {
      "name": "Polar H10",
      "address": "AA:BB:CC:DD:EE:FF",
      "type": "heart_rate_monitor"
    }
  ],
  "lthr": 155,
  "ftp": 250,
  "last_updated": "2025-01-01T10:00:00.000000"
}
```

## Supported Device Types

| Type identifier | BLE Service | Examples |
|-----------------|-------------|---------|
| `heart_rate_monitor` | HRS 0x180D | Polar H10, Garmin HRM-Pro |
| `trainer` | CPS 0x1818 / FTMS 0x1826 | Wahoo KICKR, Elite Muin+, Stages |
| `unknown` | — | Any other BLE device |

## License

MIT

