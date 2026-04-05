"""Discover per-day capture folders under the recorder output root."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_IMAGE_NAME = re.compile(r"^\d{6}\.(?:jpg|jpeg)$", re.IGNORECASE)


@dataclass(frozen=True)
class DayRecord:
    day: date
    has_video: bool
    images: tuple[str, ...]


def list_recorded_days(root: Path) -> list[DayRecord]:
    """Days that have a summary video and/or numbered JPEGs."""
    root = root.resolve()
    if not root.is_dir():
        return []
    rows: list[DayRecord] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            d = date.fromisoformat(child.name)
        except ValueError:
            continue
        has_video = (child / "summary.mp4").is_file()
        images = sorted(
            p.name
            for p in child.iterdir()
            if p.is_file() and _IMAGE_NAME.fullmatch(p.name)
        )
        if has_video or images:
            rows.append(
                DayRecord(day=d, has_video=has_video, images=tuple(images))
            )
    rows.sort(key=lambda r: r.day, reverse=True)
    return rows


def get_day_record(root: Path, day: date) -> DayRecord | None:
    folder = (root.resolve() / day.isoformat())
    if not folder.is_dir():
        return None
    has_video = (folder / "summary.mp4").is_file()
    images = sorted(
        p.name
        for p in folder.iterdir()
        if p.is_file() and _IMAGE_NAME.fullmatch(p.name)
    )
    if not has_video and not images:
        return None
    return DayRecord(day=day, has_video=has_video, images=tuple(images))


def media_file_path(root: Path, day: date, filename: str) -> Path | None:
    """Resolve a single file under ``day`` if it is an allowed capture file."""
    if "/" in filename or "\\" in filename or filename in (".", ".."):
        return None
    root_r = root.resolve()
    day_dir = (root_r / day.isoformat()).resolve()
    try:
        day_dir.relative_to(root_r)
    except ValueError:
        return None
    if not day_dir.is_dir():
        return None
    if filename == "summary.mp4":
        path = day_dir / filename
        return path if path.is_file() else None
    if not _IMAGE_NAME.fullmatch(filename):
        return None
    path = day_dir / filename
    return path if path.is_file() else None
