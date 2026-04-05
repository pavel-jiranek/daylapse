"""Entry point for the motion-gated capture service."""

from __future__ import annotations

import logging
import signal
import sys

from app.capture import CaptureService
from app.config import Settings

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    cam_log = (
        "auto"
        if settings.camera_index is None
        else str(settings.camera_index)
    )
    logger.info(
        "Starting capture service (camera=%s, out=%s, cap_fps=%s, video_fps=%s)",
        cam_log,
        settings.output_dir,
        settings.capture_fps,
        settings.video_fps,
    )

    service = CaptureService(settings)

    def _stop(*_args: object) -> None:
        logger.info("Shutdown signal received; exiting.")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    service.run()


if __name__ == "__main__":
    main()
