"""
Cardio Trainer – Application Entry Point

Bootstraps the PyQt5 application, configures logging, loads the sensor
configuration, and launches the main window.

Usage::

    python main.py [--log-level LEVEL]

Supported log levels: DEBUG, INFO, WARNING, ERROR (default: INFO).
"""

import argparse
import logging
import sys

from PyQt5.QtWidgets import QApplication

from config.config_manager import ConfigManager
from modules.ui.main_window import MainWindow


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cardio Trainer – cycling training application"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set the logging verbosity level (default: INFO)",
    )
    return parser.parse_args()


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    """Application entry point.

    Returns:
        Process exit code (0 on clean exit).
    """
    args = _parse_args()
    _configure_logging(args.log_level)

    logger = logging.getLogger(__name__)
    logger.info("Starting Cardio Trainer")

    app = QApplication(sys.argv)
    app.setApplicationName("Cardio Trainer")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("seradamus-pixel")

    config_manager = ConfigManager()
    window = MainWindow(config_manager=config_manager)
    window.show()

    logger.info("Main window displayed")
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
