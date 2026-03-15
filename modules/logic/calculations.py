"""
Data Calculations

Provides real-time processing utilities for cycling metrics including:
  - Heart rate zone classification
  - Power zone (W/kg) calculation
  - Normalised power (NP) and Intensity Factor (IF)
  - Training Stress Score (TSS) estimation
  - Cadence smoothing via a rolling average
  - Calorie expenditure estimation
"""

import logging
import math
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)

# Heart rate zone boundaries as percentage of maximum HR
_HR_ZONE_BOUNDARIES = [0.60, 0.70, 0.80, 0.90, 1.00]
_HR_ZONE_NAMES = ["Zone 1 – Recovery", "Zone 2 – Aerobic", "Zone 3 – Tempo",
                   "Zone 4 – Threshold", "Zone 5 – VO2max"]

# Power zone boundaries as percentage of FTP
_POWER_ZONE_BOUNDARIES = [0.55, 0.75, 0.90, 1.05, 1.20, 1.50]
_POWER_ZONE_NAMES = [
    "Zone 1 – Active Recovery",
    "Zone 2 – Endurance",
    "Zone 3 – Tempo",
    "Zone 4 – Threshold",
    "Zone 5 – VO2max",
    "Zone 6 – Anaerobic",
    "Zone 7 – Neuromuscular",
]


class DataCalculator:
    """Stateful calculator for real-time cycling metrics.

    Args:
        max_hr: Athlete's maximum heart rate (BPM).
        ftp: Functional threshold power (watts).
        weight_kg: Athlete's body weight (kilograms).

    Example::

        calc = DataCalculator(max_hr=185, ftp=250, weight_kg=75)
        calc.add_power_sample(240)
        np = calc.normalised_power()
    """

    def __init__(
        self,
        max_hr: int = 185,
        ftp: int = 250,
        weight_kg: float = 75.0,
    ) -> None:
        self.max_hr = max_hr
        self.ftp = ftp
        self.weight_kg = weight_kg

        # Rolling windows
        self._power_window: deque[int] = deque(maxlen=30)       # ~30 s at 1 Hz
        self._cadence_window: deque[float] = deque(maxlen=5)    # smoothing
        self._hr_window: deque[int] = deque(maxlen=5)

        # Session accumulators
        self._total_power_samples: int = 0
        self._sum_power_4th: float = 0.0   # for NP calculation
        self._elapsed_seconds: float = 0.0

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------

    def add_power_sample(self, watts: int) -> None:
        """Record a new power reading.

        Args:
            watts: Instantaneous power in watts (non-negative).
        """
        watts = max(0, int(watts))
        self._power_window.append(watts)
        self._sum_power_4th += watts ** 4
        self._total_power_samples += 1

    def add_cadence_sample(self, rpm: float) -> None:
        """Record a new cadence reading.

        Args:
            rpm: Pedalling cadence in revolutions per minute.
        """
        self._cadence_window.append(max(0.0, float(rpm)))

    def add_hr_sample(self, bpm: int) -> None:
        """Record a new heart rate reading.

        Args:
            bpm: Heart rate in beats per minute.
        """
        self._hr_window.append(max(0, int(bpm)))

    def tick(self, seconds: float = 1.0) -> None:
        """Advance the internal elapsed-time counter.

        Should be called once per second (or with the real elapsed delta).

        Args:
            seconds: Time delta in seconds since the last tick.
        """
        self._elapsed_seconds += seconds

    # ------------------------------------------------------------------
    # Derived metrics
    # ------------------------------------------------------------------

    def smoothed_power(self) -> int:
        """Return the rolling average power over the last 30 samples."""
        if not self._power_window:
            return 0
        return int(sum(self._power_window) / len(self._power_window))

    def smoothed_cadence(self) -> float:
        """Return the rolling average cadence over the last 5 samples."""
        if not self._cadence_window:
            return 0.0
        return sum(self._cadence_window) / len(self._cadence_window)

    def smoothed_hr(self) -> int:
        """Return the rolling average heart rate over the last 5 samples."""
        if not self._hr_window:
            return 0
        return int(sum(self._hr_window) / len(self._hr_window))

    def normalised_power(self) -> int:
        """Calculate normalised power (NP) using the 30-second rolling average.

        Returns:
            Normalised power in watts, or 0 when fewer than 30 samples exist.
        """
        if self._total_power_samples < 30:
            return 0
        np_raw = (self._sum_power_4th / self._total_power_samples) ** 0.25
        return int(round(np_raw))

    def intensity_factor(self) -> float:
        """Calculate Intensity Factor (IF = NP / FTP).

        Returns:
            Intensity factor as a float, or 0.0 when FTP is zero.
        """
        if self.ftp <= 0:
            return 0.0
        return self.normalised_power() / self.ftp

    def tss(self) -> float:
        """Estimate Training Stress Score (TSS).

        TSS = (elapsed_s × NP × IF) / (FTP × 3600) × 100

        Returns:
            TSS as a float, or 0.0 when not enough data is available.
        """
        np = self.normalised_power()
        if_ = self.intensity_factor()
        if self.ftp <= 0 or self._elapsed_seconds <= 0:
            return 0.0
        return (self._elapsed_seconds * np * if_) / (self.ftp * 3600) * 100

    def watts_per_kg(self) -> float:
        """Return the smoothed power-to-weight ratio.

        Returns:
            W/kg as a float, or 0.0 when weight is zero.
        """
        if self.weight_kg <= 0:
            return 0.0
        return self.smoothed_power() / self.weight_kg

    def calories_burned(self) -> float:
        """Estimate total calories burned from accumulated work.

        Uses a gross efficiency of 25 % (typical for cycling).

        Returns:
            Calories (kcal) as a float.
        """
        # Work (J) = average power × elapsed time; 1 kcal ≈ 4184 J; efficiency ~25 %
        avg_power = (
            self._sum_power_4th ** 0.25 if self._total_power_samples > 0 else 0
        )
        joules = avg_power * self._elapsed_seconds
        return joules / (4184 * 0.25)

    def hr_zone(self, current_hr: int) -> tuple[int, str]:
        """Classify *current_hr* into a heart rate zone.

        Args:
            current_hr: Instantaneous heart rate in BPM.

        Returns:
            A tuple of (zone_number, zone_name), 1-indexed.  Zone 0 is
            returned when below zone 1.
        """
        ratio = current_hr / self.max_hr if self.max_hr > 0 else 0.0
        for idx, boundary in enumerate(_HR_ZONE_BOUNDARIES):
            if ratio <= boundary:
                return idx + 1, _HR_ZONE_NAMES[idx]
        return 5, _HR_ZONE_NAMES[4]

    def power_zone(self, current_watts: int) -> tuple[int, str]:
        """Classify *current_watts* into a power zone.

        Args:
            current_watts: Instantaneous power in watts.

        Returns:
            A tuple of (zone_number, zone_name), 1-indexed.
        """
        ratio = current_watts / self.ftp if self.ftp > 0 else 0.0
        for idx, boundary in enumerate(_POWER_ZONE_BOUNDARIES):
            if ratio <= boundary:
                return idx + 1, _POWER_ZONE_NAMES[idx]
        return 7, _POWER_ZONE_NAMES[6]

    def reset_session(self) -> None:
        """Clear all accumulated session data."""
        self._power_window.clear()
        self._cadence_window.clear()
        self._hr_window.clear()
        self._total_power_samples = 0
        self._sum_power_4th = 0.0
        self._elapsed_seconds = 0.0
        logger.info("Session data reset")


def speed_from_power(watts: int, cda: float = 0.32, rho: float = 1.225,
                     crr: float = 0.004, mass_kg: float = 80.0,
                     grade: float = 0.0) -> float:
    """Estimate cycling speed from power output using a physical model.

    Solves P = F_aero × v + F_roll × v + F_grav × v for velocity using
    Newton–Raphson iteration.

    Args:
        watts: Power output in watts.
        cda: Drag coefficient × frontal area (m²).
        rho: Air density (kg/m³).
        crr: Coefficient of rolling resistance.
        mass_kg: Total rider + bike mass (kg).
        grade: Road gradient as a fraction (0.05 = 5 % uphill).

    Returns:
        Speed in km/h.
    """
    g = 9.81
    v = 5.0  # initial guess m/s
    for _ in range(50):
        f_aero = 0.5 * cda * rho * v ** 2
        f_roll = crr * mass_kg * g * math.cos(math.atan(grade))
        f_grav = mass_kg * g * math.sin(math.atan(grade))
        p_calc = (f_aero + f_roll + f_grav) * v
        dP_dv = 1.5 * cda * rho * v ** 2 + f_roll + f_grav
        delta = (p_calc - watts) / dP_dv if dP_dv != 0 else 0
        v -= delta
        v = max(0.0, v)
        if abs(delta) < 1e-4:
            break
    return v * 3.6  # m/s → km/h
