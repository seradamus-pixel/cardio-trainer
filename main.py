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

# Import menedżera konfiguracji i głównego okna aplikacji
from config.config_manager import ConfigManager
from modules.ui.main_window import MainWindow


def _parse_args() -> argparse.Namespace:
    """
    Parsuje argumenty linii poleceń.
    
    Obsługuje opcjonalny parametr --log-level do kontrolowania poziomu szczegółowości
    logów (DEBUG, INFO, WARNING, ERROR).
    
    Returns:
        argparse.Namespace: Sparsowane argumenty
    """
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
    """
    Konfiguruje system logowania aplikacji.
    
    Ustawia poziom szczegółowości, format logów oraz format czasu.
    
    Args:
        level: Poziom logowania (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    """
    Główny punkt wejścia aplikacji.
    
    Etapy inicjalizacji:
    1. Parsowanie argumentów linii poleceń
    2. Konfiguracja systemu logowania
    3. Inicjalizacja aplikacji PyQt5
    4. Załadowanie konfiguracji czujników
    5. Wyświetlenie głównego okna
    6. Uruchomienie pętli zdarzeń

    Returns:
        int: Kod wyjścia procesu (0 przy normalnym zamknięciu)
    """
    # Parsuj argumenty wiersza poleceń
    args = _parse_args()
    
    # Skonfiguruj system logowania na wybranym poziomie
    _configure_logging(args.log_level)

    # Pobierz logger dla tego modułu
    logger = logging.getLogger(__name__)
    logger.info("Starting Cardio Trainer")

# Punkt wejścia - uruchom aplikację i wyjdź z kodem zwróconego statusu
    # Inicjalizuj aplikację PyQt5
    app = QApplication(sys.argv)
    app.setApplicationName("Cardio Trainer")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("seradamus-pixel")

    # Wczytaj konfigurację czujników i stwórz główne okno
    config_manager = ConfigManager()
    window = MainWindow(config_manager=config_manager)
    window.show()

    # Zaloguj wyświetlenie okna i uruchom pętlę zdarzeń
    logger.info("Main window displayed")
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
