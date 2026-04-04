"""Frame-difference motion scoring and sustained-motion / sustained-still logic."""

from __future__ import annotations

from collections import deque

import cv2
import numpy as np


class MotionGate:
    """
    Observes per-frame motion scores; reports when to start/stop capture.

    Motion is detected when at least ``trigger_hits`` of the last ``window`` scores
    exceed ``motion_threshold``. Capture ends when at least ``still_hits`` of the
    last ``still_window`` scores fall below ``still_max``.
    """

    def __init__(
        self,
        *,
        window: int,
        trigger_hits: int,
        motion_threshold: float,
        still_window: int,
        still_hits: int,
        still_max: float,
        analysis_width: int,
    ) -> None:
        self._window = window
        self._trigger_hits = trigger_hits
        self._motion_threshold = motion_threshold
        self._still_window = still_window
        self._still_hits = still_hits
        self._still_max = still_max
        self._analysis_width = analysis_width
        self._prev_gray: np.ndarray | None = None
        self._scores: deque[float] = deque(maxlen=max(window, still_window))

    def _prepare_gray(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if w != self._analysis_width:
            scale = self._analysis_width / float(w)
            new_h = max(1, int(round(h * scale)))
            small = cv2.resize(
                frame, (self._analysis_width, new_h), interpolation=cv2.INTER_AREA
            )
        else:
            small = frame
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        cv2.GaussianBlur(gray, (5, 5), 0, dst=gray)
        return gray

    def score_frame(self, frame: np.ndarray) -> float:
        gray = self._prepare_gray(frame)
        if self._prev_gray is None:
            self._prev_gray = gray
            return 0.0
        diff = cv2.absdiff(gray, self._prev_gray)
        self._prev_gray = gray
        _, mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        changed = float(np.count_nonzero(mask))
        total = float(mask.size)
        return changed / total if total else 0.0

    def update(self, frame: np.ndarray) -> None:
        self._scores.append(self.score_frame(frame))

    def should_start_capture(self) -> bool:
        if len(self._scores) < self._window:
            return False
        recent = list(self._scores)[-self._window :]
        hits = sum(1 for s in recent if s >= self._motion_threshold)
        return hits >= self._trigger_hits

    def should_stop_capture(self) -> bool:
        if len(self._scores) < self._still_window:
            return False
        recent = list(self._scores)[-self._still_window :]
        stills = sum(1 for s in recent if s <= self._still_max)
        return stills >= self._still_hits
