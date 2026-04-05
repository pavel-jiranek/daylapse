"""Load settings from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    """Runtime configuration (see env vars in docker-compose)."""

    camera_index: int | None
    camera_index_max: int
    output_dir: str
    capture_fps: float
    video_fps: float
    motion_window_frames: int
    motion_trigger_min_hits: int
    motion_score_threshold: float
    recording_quiet_seconds: float
    analysis_width: int
    video_codec: str
    image_quality: int
    timezone: str | None

    @staticmethod
    def from_env() -> "Settings":
        raw_cam = os.environ.get("CAMERA_INDEX")
        if raw_cam is None:
            camera_index: int | None = 0
        else:
            stripped = raw_cam.strip()
            if stripped == "":
                camera_index = 0
            elif stripped.lower() in ("auto", "none"):
                camera_index = None
            else:
                camera_index = int(stripped)
        return Settings(
            camera_index=None,
            camera_index_max=max(0, _int("CAMERA_INDEX_MAX", 10)),
            output_dir=os.environ.get("OUTPUT_DIR", "./data/captures"),
            capture_fps=_float("CAPTURE_FPS", 8.0),
            video_fps=_float("VIDEO_FPS", 30.0),
            motion_window_frames=max(1, _int("MOTION_WINDOW_FRAMES", 5)),
            motion_trigger_min_hits=max(
                1, _int("MOTION_TRIGGER_MIN_HITS", 3)
            ),
            motion_score_threshold=_float("MOTION_SCORE_THRESHOLD", 0.02),
            recording_quiet_seconds=max(
                0.0, _float("RECORDING_QUIET_SECONDS", 60.0)
            ),
            analysis_width=max(64, _int("ANALYSIS_WIDTH", 320)),
            video_codec=os.environ.get("VIDEO_CODEC", "libx264"),
            image_quality=max(1, min(100, _int("JPEG_QUALITY", 92))),
            timezone=os.environ.get("TZ") or None,
        )
