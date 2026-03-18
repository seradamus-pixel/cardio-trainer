#!/usr/bin/env python3
"""
main_training.py

Entry point for trainero2 – live training session interface (Part 2).

Usage
-----
    python main_training.py [--log-level {DEBUG,INFO,WARNING,ERROR}]

The application reads sensor MAC addresses and athlete settings from
``config/sensors.json``, automatically connects to the configured BLE
devices, and displays a large real-time training interface.

Run ``python main.py`` first to scan for and configure sensor devices.
"""

import argparse
import logging
import sys

from PyQt5.QtWidgets import QApplication

from modules.trainer_ui import TrainerUI
from modules.ui.styles import APP_STYLESHEET


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="trainero2 – live training session interface"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    app = QApplication(sys.argv)
    app.setApplicationName("trainero2")
    app.setOrganizationName("seradamus-pixel")
    app.setStyleSheet(APP_STYLESHEET)

    window = TrainerUI()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
