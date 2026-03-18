"""
Data Recorder

Records real-time training data (HR, power, cadence) sampled during a session
and persists a structured workout summary to ``data/workouts/`` at the end of
the session.

The summary includes:
- Session timestamps and duration
- Average / max / min for HR, power, and cadence
- Heart-rate drift (BPM/min)
- Total energy expenditure (kJ)
- %FTP averages
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_WORKOUTS_DIR = Path(__file__).parent.parent / "data" / "workouts"


class SessionRecorder:
    """Records training data and computes post-session summaries.

    Args:
        ftp: Athlete's functional threshold power (watts), used to compute
            %FTP statistics.

    Example::

        recorder = SessionRecorder(ftp=250)
        recorder.start()
        for each_second:
            recorder.add_sample(hr=145, power=230, cadence=90.0)
        summary = recorder.stop()
        path = recorder.save(summary)
    """

    def __init__(self, ftp: int = 250) -> None:
        self.ftp = max(1, int(ftp))
        self._samples: list[dict] = []
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._active: bool = False

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Begin a new recording session (clears previous data)."""
        self._start_time = datetime.now()
        self._end_time = None
        self._samples = []
        self._active = True
        logger.info("Session recording started at %s", self._start_time.isoformat())

    def stop(self) -> dict:
        """Stop recording and return the computed session summary.

        Returns:
            Dictionary with session statistics (see :meth:`_compute_summary`).
        """
        if self._active:
            self._end_time = datetime.now()
            self._active = False
        summary = self._compute_summary()
        logger.info(
            "Session stopped – duration %.0f s, %d samples",
            summary.get("duration_seconds", 0),
            len(self._samples),
        )
        return summary

    def reset(self) -> None:
        """Clear all accumulated data without saving."""
        self._samples = []
        self._start_time = None
        self._end_time = None
        self._active = False

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------

    def add_sample(
        self,
        hr: int = 0,
        power: int = 0,
        cadence: float = 0.0,
    ) -> None:
        """Record one data sample.

        Samples are only stored while the recorder is active (after
        :meth:`start` and before :meth:`stop`).

        Args:
            hr: Heart rate in BPM (0 = no data).
            power: Power in watts (0 = no data).
            cadence: Cadence in RPM (0 = no data).
        """
        if not self._active:
            return
        self._samples.append({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "hr": max(0, int(hr)),
            "power": max(0, int(power)),
            "cadence": round(max(0.0, float(cadence)), 1),
        })

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, summary: Optional[dict] = None) -> str:
        """Save the session summary JSON to the workouts directory.

        Args:
            summary: Pre-computed summary dict; if ``None`` it is computed now.

        Returns:
            Absolute path string of the written file.
        """
        if summary is None:
            summary = self._compute_summary()

        _WORKOUTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = (self._start_time or datetime.now()).strftime("%Y%m%d_%H%M%S")
        filepath = _WORKOUTS_DIR / f"workout_{ts}.json"

        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)

        logger.info("Workout saved → %s", filepath)
        return str(filepath)

    # ------------------------------------------------------------------
    # Summary computation
    # ------------------------------------------------------------------

    def _compute_summary(self) -> dict:
        start_iso = self._start_time.isoformat() if self._start_time else ""
        end_iso = (
            self._end_time.isoformat() if self._end_time else datetime.now().isoformat()
        )

        duration_s = 0.0
        if self._start_time and self._end_time:
            duration_s = (self._end_time - self._start_time).total_seconds()

        hrs = [s["hr"] for s in self._samples if s["hr"] > 0]
        powers = [s["power"] for s in self._samples if s["power"] > 0]
        cadences = [s["cadence"] for s in self._samples if s["cadence"] > 0]

        avg_power = sum(powers) / len(powers) if powers else 0.0
        energy_kj = avg_power * duration_s / 1000.0

        # HR drift: (last sample HR − first sample HR) / elapsed minutes
        hr_drift = 0.0
        if len(hrs) >= 2 and duration_s >= 60:
            hr_drift = (hrs[-1] - hrs[0]) / (duration_s / 60.0)

        return {
            "start_time": start_iso,
            "end_time": end_iso,
            "duration_seconds": round(duration_s, 1),
            "ftp": self.ftp,
            "heart_rate": {
                "average": round(sum(hrs) / len(hrs)) if hrs else 0,
                "max": max(hrs) if hrs else 0,
                "min": min(hrs) if hrs else 0,
                "drift_bpm_per_min": round(hr_drift, 2),
            },
            "power": {
                "average": round(avg_power),
                "max": max(powers) if powers else 0,
                "min": min(powers) if powers else 0,
                "avg_pct_ftp": round(avg_power / self.ftp * 100, 1),
            },
            "cadence": {
                "average": round(sum(cadences) / len(cadences), 1) if cadences else 0.0,
                "max": round(max(cadences), 1) if cadences else 0.0,
            },
            "energy_kj": round(energy_kj, 1),
            "samples_count": len(self._samples),
        }

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """``True`` while a session is in progress."""
        return self._active

    @property
    def elapsed_seconds(self) -> float:
        """Seconds elapsed since :meth:`start` was called (0 if not started)."""
        if self._start_time is None:
            return 0.0
        end = self._end_time or datetime.now()
        return (end - self._start_time).total_seconds()
