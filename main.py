#!/usr/bin/env python3
"""
main.py

Entry point for trainero2 – device setup interface (Part 1).

Usage
-----
    python main.py [--log-level {DEBUG,INFO,WARNING,ERROR}]

Scans for nearby BLE sensors (Heart Rate Monitor, Power Meter, Smart Trainer),
lets the user select and connect to each, and saves the chosen MAC addresses to
``config/sensors.json`` for use by the training session.

Run ``python main_training.py`` next to start the live training session.
"""

import argparse
import logging
import sys

from PyQt5.QtWidgets import QApplication

from config.config_manager import ConfigManager
from modules.ui.main_window import MainWindow
from modules.ui.styles import APP_STYLESHEET


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="trainero2 – device setup interface"
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

    config = ConfigManager()
    window = MainWindow(config_manager=config)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
