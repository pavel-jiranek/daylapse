"""End-of-day: images → video via ffmpeg, then delete JPEGs on success."""

from __future__ import annotations

import logging
import subprocess
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


def _list_jpegs(day_dir: Path) -> list[Path]:
    files: list[Path] = []
    for p in day_dir.iterdir():
        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg"):
            files.append(p)
    files.sort(key=lambda x: x.name)
    return files


def build_day_video(
    day_dir: Path,
    *,
    video_fps: float,
    video_codec: str,
    output_name: str = "day_summary.mp4",
) -> bool:
    """
    Encode all JPEGs in ``day_dir`` into a single MP4. Returns True on success.

    On success, JPEGs are removed. On failure, images are left untouched.
    """
    day_dir = day_dir.resolve()
    if not day_dir.is_dir():
        logger.warning("Day directory missing: %s", day_dir)
        return False

    jpegs = _list_jpegs(day_dir)
    if not jpegs:
        logger.info("No JPEGs in %s; skipping video build.", day_dir)
        return True

    out = day_dir / output_name
    if out.exists():
        logger.warning("Output already exists, skipping: %s", out)
        return False

    # glob order is lexicographic; zero-padded names sort correctly
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-framerate",
        str(video_fps),
        "-pattern_type",
        "glob",
        "-i",
        "*.jpg",
        "-c:v",
        video_codec,
        "-pix_fmt",
        "yuv420p",
        str(out.name),
    ]

    try:
        subprocess.run(cmd, check=True, cwd=str(day_dir))
    except subprocess.CalledProcessError as e:
        logger.error("ffmpeg failed for %s: %s", day_dir, e)
        if out.exists():
            out.unlink(missing_ok=True)
        return False

    for p in jpegs:
        try:
            p.unlink()
        except OSError as err:
            logger.error("Failed to delete %s: %s", p, err)
            return False

    logger.info("Archived %s (%d frames) → %s", day_dir.name, len(jpegs), out.name)
    return True


def process_day_if_due(
    output_root: Path,
    day: date,
    *,
    video_fps: float,
    video_codec: str,
) -> None:
    """Build video for ``day`` under ``output_root / YYYY-MM-DD``."""
    folder = output_root / day.isoformat()
    build_day_video(folder, video_fps=video_fps, video_codec=video_codec)
