"""
Text User Interface

Interactive text menu for the BLE scanner application.

Allows the user to:
  - Scan for nearby BLE devices and view them with RSSI and device type.
  - Add discovered devices to the saved list in ``config/devices.json``.
  - Remove saved devices from the list.
  - Set LTHR (Lactate Threshold Heart Rate) and FTP (Functional Threshold Power).
"""

import asyncio
import logging
from typing import List, Optional

from modules.ble_scanner import ScannedDevice, scan_devices
from modules.device_manager import DeviceManager

logger = logging.getLogger(__name__)

_LINE = "-" * 78
_HEADER = "=" * 60


def _print_header() -> None:
    print("\n" + _HEADER)
    print("   CARDIO TRAINER – Skaner BLE")
    print(_HEADER)


def _print_scanned_devices(devices: List[ScannedDevice]) -> None:
    """Print a numbered table of scanned BLE devices."""
    if not devices:
        print("  Nie znaleziono żadnych urządzeń.")
        return
    print(
        f"\n{'Nr':>3}  {'Nazwa':<28}  {'Adres MAC':<19}  {'RSSI':>6}  Typ"
    )
    print(_LINE)
    for i, d in enumerate(devices, 1):
        print(
            f"  {i:>2}  {d.name:<28}  {d.address:<19}  {d.rssi:>4} dBm  "
            f"{d.device_type_label()}"
        )


def _print_saved_devices(manager: DeviceManager) -> None:
    """Print a numbered table of saved devices."""
    devices = manager.get_devices()
    print(f"\n{'Nr':>3}  {'Nazwa':<28}  {'Adres MAC':<19}  Typ")
    print(_LINE)
    if not devices:
        print("  Brak zapisanych urządzeń.")
    else:
        for i, d in enumerate(devices, 1):
            print(
                f"  {i:>2}  {d.get('name', ''):<28}  "
                f"{d.get('address', ''):<19}  {d.get('type', '')}"
            )


def _print_config(manager: DeviceManager) -> None:
    """Print current LTHR and FTP settings."""
    print(f"  LTHR : {manager.get_lthr()} bpm")
    print(f"  FTP  : {manager.get_ftp()} W")
    print(f"  Plik : {manager.config_path}")


def _ask_int(prompt: str) -> Optional[int]:
    """Prompt the user for an integer value.  Returns *None* on invalid input."""
    raw = input(prompt).strip()
    try:
        return int(raw)
    except ValueError:
        return None


async def run_ui(manager: DeviceManager, scan_duration: float = 10.0) -> None:
    """Run the interactive text menu.

    Args:
        manager: :class:`~modules.device_manager.DeviceManager` instance used
            to persist device and configuration data.
        scan_duration: BLE scan duration in seconds.
    """
    scanned: List[ScannedDevice] = []

    while True:
        _print_header()
        print("\n  Opcje:")
        print("  [1] Skanuj urządzenia BLE")
        print("  [2] Dodaj urządzenie do listy zapisanych")
        print("  [3] Usuń urządzenie z listy zapisanych")
        print("  [4] Pokaż zapisane urządzenia")
        print("  [5] Ustaw LTHR")
        print("  [6] Ustaw FTP")
        print("  [7] Pokaż konfigurację")
        print("  [0] Wyjście")
        print()

        choice = input("  Wybierz opcję: ").strip()

        if choice == "1":
            print(f"\n  Skanowanie przez {scan_duration:.0f} sekund...")
            try:
                scanned = await scan_devices(duration=scan_duration)
                _print_scanned_devices(scanned)
            except Exception as exc:
                print(f"\n  BŁĄD skanowania: {exc}")
                logger.exception("Scan error: %s", exc)

        elif choice == "2":
            if not scanned:
                print("\n  Najpierw przeprowadź skanowanie (opcja 1).")
            else:
                _print_scanned_devices(scanned)
                idx = _ask_int("\n  Podaj numer urządzenia do dodania: ")
                if idx is None or not (1 <= idx <= len(scanned)):
                    print("\n  Nieprawidłowy numer.")
                else:
                    d = scanned[idx - 1]
                    if manager.add_device(d.address, d.name, d.device_type):
                        print(f"\n  ✓ Dodano: {d.name} ({d.address})")
                    else:
                        print(f"\n  Urządzenie {d.address} już jest na liście.")

        elif choice == "3":
            saved = manager.get_devices()
            if not saved:
                print("\n  Brak zapisanych urządzeń.")
            else:
                _print_saved_devices(manager)
                idx = _ask_int("\n  Podaj numer urządzenia do usunięcia: ")
                if idx is None or not (1 <= idx <= len(saved)):
                    print("\n  Nieprawidłowy numer.")
                else:
                    addr = saved[idx - 1]["address"]
                    name = saved[idx - 1]["name"]
                    if manager.remove_device(addr):
                        print(f"\n  ✓ Usunięto: {name} ({addr})")

        elif choice == "4":
            print("\n  Zapisane urządzenia:")
            _print_saved_devices(manager)

        elif choice == "5":
            val = _ask_int("\n  Podaj wartość LTHR (bpm): ")
            if val is None or val < 0:
                print("\n  Nieprawidłowa wartość (musi być nieujemną liczbą całkowitą).")
            else:
                manager.set_lthr(val)
                print(f"\n  ✓ LTHR ustawiony na {val} bpm")

        elif choice == "6":
            val = _ask_int("\n  Podaj wartość FTP (W): ")
            if val is None or val < 0:
                print("\n  Nieprawidłowa wartość (musi być nieujemną liczbą całkowitą).")
            else:
                manager.set_ftp(val)
                print(f"\n  ✓ FTP ustawiony na {val} W")

        elif choice == "7":
            print("\n  Konfiguracja:")
            _print_config(manager)

        elif choice == "0":
            print("\n  Do widzenia!\n")
            break

        else:
            print("\n  Nieznana opcja. Wybierz numer z menu.")

        if choice != "0":
            input("\n  Naciśnij Enter, aby kontynuować...")

