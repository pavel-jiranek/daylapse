"""Load viewer settings from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    """Runtime configuration (OUTPUT_DIR aligns with recorder / docker-compose)."""

    output_dir: str
    host: str
    port: int

    @property
    def captures_root(self) -> Path:
        return Path(self.output_dir).expanduser().resolve()

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            output_dir=os.environ.get("OUTPUT_DIR", "./data/captures"),
            host=os.environ.get("VIEWER_HOST", "127.0.0.1"),
            port=_int("VIEWER_PORT", 8000),
        )
