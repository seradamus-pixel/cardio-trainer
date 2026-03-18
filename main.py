"""
Cardio Trainer – Main Entry Point

Runs the interactive BLE scanner application.

Usage::

    python main.py [--log-level {DEBUG,INFO,WARNING,ERROR}] [--scan-duration SECONDS]
"""

import argparse
import asyncio
import logging
import sys

from modules.device_manager import DeviceManager
from modules.ui import run_ui


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.WARNING),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cardio Trainer – BLE scanner for fitness devices",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    parser.add_argument(
        "--scan-duration",
        type=float,
        default=10.0,
        metavar="SECONDS",
        help="BLE scan duration in seconds",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _setup_logging(args.log_level)

    manager = DeviceManager()

    try:
        asyncio.run(run_ui(manager, scan_duration=args.scan_duration))
    except KeyboardInterrupt:
        print("\n  Przerwano przez użytkownika.")
        sys.exit(0)


if __name__ == "__main__":
    main()