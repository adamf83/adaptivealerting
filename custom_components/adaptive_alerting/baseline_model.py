from __future__ import annotations

import logging
import statistics
from collections import deque

_LOGGER = logging.getLogger(__name__)

MAX_SAMPLES = 10_000  # Cap memory usage


class BaselineModel:
    """
    Z-score baseline model.
    Stores a rolling window of historical values and computes
    mean + std deviation to score incoming readings.
    """

    def __init__(self, sensitivity: float) -> None:
        self.sensitivity = sensitivity
        self._samples: deque[float] = deque(maxlen=MAX_SAMPLES)
        self._is_ready = False  # True once we have enough data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_sample(self, value: float) -> None:
        """Record a new sensor reading into the model."""
        self._samples.append(value)
        if len(self._samples) >= 30:
            self._is_ready = True

    def evaluate(self, value: float) -> dict:
        """
        Score a value against the learned baseline.

        Returns a dict with:
          - is_anomaly (bool)
          - z_score (float)
          - mean (float)
          - std_dev (float)
          - is_ready (bool)
        """
        if not self._is_ready:
            return {
                "is_anomaly": False,
                "z_score": 0.0,
                "mean": 0.0,
                "std_dev": 0.0,
                "is_ready": False,
            }

        mean = statistics.mean(self._samples)
        try:
            std_dev = statistics.stdev(self._samples)
        except statistics.StatisticsError:
            std_dev = 0.0

        if std_dev == 0:
            z_score = 0.0
        else:
            z_score = abs((value - mean) / std_dev)

        return {
            "is_anomaly": z_score >= self.sensitivity,
            "z_score": round(z_score, 3),
            "mean": round(mean, 3),
            "std_dev": round(std_dev, 3),
            "is_ready": True,
        }

    def reset(self) -> None:
        """Wipe all learned data."""
        self._samples.clear()
        self._is_ready = False

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise for storage."""
        return {
            "samples": list(self._samples),
            "sensitivity": self.sensitivity,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BaselineModel":
        """Deserialise from storage."""
        from .const import DEFAULT_SENSITIVITY
        model = cls(sensitivity=data.get("sensitivity", DEFAULT_SENSITIVITY))
        for s in data.get("samples", []):
            model._samples.append(s)
        if len(model._samples) >= 30:
            model._is_ready = True
        return model
