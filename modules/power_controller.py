"""
Power Controller

Manages the smart trainer's operating mode, automatically switching between
ERG (constant power) and Resistance mode based on live cadence readings.
Hysteresis prevents rapid mode oscillation.

Mode-switching logic
--------------------
- **ERG → Resistance**: cadence drops below ``CADENCE_LOW_RPM`` for
  ``DEBOUNCE_SAMPLES`` consecutive ticks.
- **Resistance → ERG**: cadence rises above ``CADENCE_HIGH_RPM`` for
  ``DEBOUNCE_SAMPLES`` consecutive ticks.
- While in Resistance mode the trainer is set to ``RECOVERY_RESISTANCE``
  percent so the rider can spin up again easily.
"""

import logging
from enum import Enum, auto
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

# Cadence thresholds (RPM) for automatic mode switching
CADENCE_LOW_RPM: float = 20.0   # switch to Resistance when cadence drops below
CADENCE_HIGH_RPM: float = 25.0  # switch back to ERG when cadence recovers above

# Resistance level applied during recovery (0–100 %)
RECOVERY_RESISTANCE: int = 5

# Number of consecutive ticks that must breach the threshold before switching
DEBOUNCE_SAMPLES: int = 3


class ControlMode(Enum):
    """Trainer operating mode."""

    ERG = auto()        # hold a constant wattage
    RESISTANCE = auto() # low resistance for recovery


class PowerController(QObject):
    """Manages ERG/Resistance mode with cadence-based auto-switching.

    The controller keeps track of the desired target power and issues
    commands to the trainer via the *ble_client* when the mode changes
    or a new target is set.

    Signals:
        mode_changed: Emitted with the new :class:`ControlMode` on switch.
        target_power_changed: Emitted with the new target watts.

    Args:
        ble_client: Any object that exposes ``set_target_power(watts)`` and
            ``set_resistance(level)`` methods.  Pass ``None`` in tests.
        parent: Optional QObject parent.

    Example::

        ctrl = PowerController(ble_client=client)
        ctrl.set_target_power(200)
        ctrl.update_cadence(18)  # triggers switch to Resistance after 3 ticks
    """

    mode_changed = pyqtSignal(object)   # ControlMode
    target_power_changed = pyqtSignal(int)

    def __init__(self, ble_client=None, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._ble_client = ble_client
        self._mode: ControlMode = ControlMode.ERG
        self._target_power: int = 0
        # Debounce counters
        self._low_count: int = 0
        self._high_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def mode(self) -> ControlMode:
        """Current operating mode."""
        return self._mode

    @property
    def target_power(self) -> int:
        """Current target power in watts (ERG mode)."""
        return self._target_power

    def set_target_power(self, watts: int) -> None:
        """Set the ERG-mode target power.

        If currently in ERG mode the command is sent to the trainer
        immediately.  The value is remembered and re-applied on the next
        automatic switch back to ERG mode.

        Args:
            watts: Target power in watts (≥ 0).
        """
        self._target_power = max(0, int(watts))
        self.target_power_changed.emit(self._target_power)
        if self._mode == ControlMode.ERG and self._ble_client:
            self._ble_client.set_target_power(self._target_power)
        logger.debug("Target power set to %d W", self._target_power)

    def update_cadence(self, cadence_rpm: float) -> None:
        """Feed a new cadence reading and potentially trigger a mode switch.

        Should be called on every cadence update (typically 1 Hz).

        Args:
            cadence_rpm: Current pedalling cadence in revolutions per minute.
        """
        if self._mode == ControlMode.ERG:
            if cadence_rpm < CADENCE_LOW_RPM:
                self._low_count += 1
                self._high_count = 0
                if self._low_count >= DEBOUNCE_SAMPLES:
                    self._switch_to_resistance()
            else:
                self._low_count = 0
        else:  # RESISTANCE
            if cadence_rpm >= CADENCE_HIGH_RPM:
                self._high_count += 1
                self._low_count = 0
                if self._high_count >= DEBOUNCE_SAMPLES:
                    self._switch_to_erg()
            else:
                self._high_count = 0

    def apply_current_mode(self) -> None:
        """Re-send the active mode command to the trainer.

        Useful after reconnection to restore the trainer's state.
        """
        if self._mode == ControlMode.ERG:
            if self._ble_client and self._target_power > 0:
                self._ble_client.set_target_power(self._target_power)
        else:
            if self._ble_client:
                self._ble_client.set_resistance(RECOVERY_RESISTANCE)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _switch_to_resistance(self) -> None:
        logger.info(
            "Switching trainer → RESISTANCE (cadence below %.0f RPM after %d ticks)",
            CADENCE_LOW_RPM, DEBOUNCE_SAMPLES,
        )
        self._mode = ControlMode.RESISTANCE
        self._low_count = 0
        if self._ble_client:
            self._ble_client.set_resistance(RECOVERY_RESISTANCE)
        self.mode_changed.emit(self._mode)

    def _switch_to_erg(self) -> None:
        logger.info(
            "Switching trainer → ERG (cadence recovered above %.0f RPM after %d ticks)",
            CADENCE_HIGH_RPM, DEBOUNCE_SAMPLES,
        )
        self._mode = ControlMode.ERG
        self._high_count = 0
        if self._ble_client and self._target_power > 0:
            self._ble_client.set_target_power(self._target_power)
        self.mode_changed.emit(self._mode)
