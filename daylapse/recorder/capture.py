"""Webcam loop: motion-gated frame capture into per-day folders."""

from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2
import numpy as np

from daylapse.recorder.config import Settings
from daylapse.recorder.day_processor import process_day_if_due
from daylapse.recorder.motion import MotionGate

logger = logging.getLogger(__name__)


def _open_video_capture(settings: Settings) -> tuple[cv2.VideoCapture, int]:
    """Open the configured camera, or scan indices 0..max until one works."""
    if settings.camera_index is not None:
        cap = cv2.VideoCapture(settings.camera_index)
        if not cap.isOpened():
            raise RuntimeError(
                f"Cannot open camera index {settings.camera_index}"
            )
        return cap, settings.camera_index
    last = settings.camera_index_max
    for idx in range(0, last + 1):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            logger.info("Using auto-discovered camera index %s", idx)
            return cap, idx
        cap.release()
    raise RuntimeError(
        f"No camera opened for indices 0..{last} "
        "(set CAMERA_INDEX or raise CAMERA_INDEX_MAX)"
    )


def _today(tz: ZoneInfo | None) -> date:
    if tz is not None:
        return datetime.now(tz).date()
    return datetime.now().astimezone().date()


def _draw_timestamp(
    frame: np.ndarray,
    tz: ZoneInfo | None,
) -> np.ndarray:
    """Return a copy of ``frame`` with date/time burned in (bottom-left)."""
    out = frame.copy()
    if tz is not None:
        now = datetime.now(tz)
    else:
        now = datetime.now().astimezone()
    text = now.strftime("%Y-%m-%d %H:%M:%S %Z")

    font = cv2.FONT_HERSHEY_SIMPLEX
    h, w = out.shape[:2]
    font_scale = max(0.45, min(1.15, w / 1280.0))
    thickness = max(1, int(round(font_scale * 2)))
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    margin = max(8, int(10 * font_scale))
    pad = max(3, int(4 * font_scale))
    x = margin
    y = h - margin - baseline
    cv2.rectangle(
        out,
        (x - pad, y - th - pad),
        (x + tw + pad, y + baseline + pad),
        (0, 0, 0),
        -1,
    )
    cv2.putText(
        out,
        text,
        (x, y),
        font,
        font_scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )
    return out


def _next_frame_index(day_dir: Path) -> int:
    best = 0
    if not day_dir.is_dir():
        return 1
    for p in day_dir.iterdir():
        if p.suffix.lower() not in (".jpg", ".jpeg"):
            continue
        stem = p.stem
        if stem.isdigit():
            best = max(best, int(stem))
    return best + 1


class CaptureService:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._tz = (
            ZoneInfo(settings.timezone) if settings.timezone else None
        )
        self._gate = MotionGate(
            window=settings.motion_window_frames,
            trigger_hits=settings.motion_trigger_min_hits,
            motion_threshold=settings.motion_score_threshold,
            analysis_width=settings.analysis_width,
        )
        self._recording_quiet_s = settings.recording_quiet_seconds
        self._capturing = False
        self._last_motion_mono: float = 0.0
        self._current_date: date | None = None
        self._frame_index = 1
        self._last_save_mono: float = 0.0
        self._lock = threading.Lock()

    def _ensure_day(self, today: date) -> Path:
        root = Path(self._s.output_dir)
        root.mkdir(parents=True, exist_ok=True)
        day_dir = root / today.isoformat()
        day_dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if self._current_date != today:
                self._current_date = today
                self._frame_index = _next_frame_index(day_dir)
        return day_dir

    def _rollover_if_needed(self, today: date) -> None:
        with self._lock:
            prev = self._current_date
        if prev is not None and prev != today:
            to_process = prev

            def job() -> None:
                process_day_if_due(
                    Path(self._s.output_dir),
                    to_process,
                    video_fps=self._s.video_fps,
                    video_codec=self._s.video_codec,
                )

            threading.Thread(target=job, name="day-rollover", daemon=True).start()

    def _maybe_save(self, frame: np.ndarray, day_dir: Path) -> None:
        interval = 1.0 / self._s.capture_fps if self._s.capture_fps > 0 else 0.0
        now = time.monotonic()
        if interval > 0 and (now - self._last_save_mono) < interval:
            return
        self._last_save_mono = now
        with self._lock:
            idx = self._frame_index
            self._frame_index = idx + 1
        path = day_dir / f"{idx:06d}.jpg"
        stamped = _draw_timestamp(frame, self._tz)
        ok = cv2.imwrite(
            str(path),
            stamped,
            (cv2.IMWRITE_JPEG_QUALITY, self._s.image_quality),
        )
        if not ok:
            logger.error("Failed to write %s", path)

    def run(self) -> None:
        cap, _ = _open_video_capture(self._s)

        try:
            while True:
                today = _today(self._tz)
                self._rollover_if_needed(today)
                day_dir = self._ensure_day(today)

                ok, frame = cap.read()
                if not ok or frame is None:
                    logger.warning("Frame grab failed; retrying")
                    time.sleep(0.2)
                    continue

                self._gate.update(frame)

                if not self._capturing:
                    if self._gate.should_start_capture():
                        self._capturing = True
                        self._last_motion_mono = time.monotonic()
                        logger.info("Motion sustained — capturing")
                else:
                    self._maybe_save(frame, day_dir)
                    if self._gate.motion_above_threshold():
                        self._last_motion_mono = time.monotonic()
                    if (
                        self._recording_quiet_s > 0
                        and time.monotonic() - self._last_motion_mono
                        >= self._recording_quiet_s
                    ):
                        self._capturing = False
                        logger.info(
                            "No motion for %.0fs — paused capture",
                            self._recording_quiet_s,
                        )

        finally:
            cap.release()
