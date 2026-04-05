"""FastAPI app: list days, stream summary MP4, browse JPEG frames."""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from daylapse.recorder.config import Settings
from daylapse.viewer.storage import get_day_record, list_recorded_days, media_file_path

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_HERE / "templates"))


def _viewer_settings() -> tuple[Path, str, int]:
    s = Settings.from_env()
    root = Path(s.output_dir).expanduser().resolve()
    host = os.environ.get("VIEWER_HOST", "127.0.0.1")
    port = int(os.environ.get("VIEWER_PORT", "8000"))
    return root, host, port


def create_app() -> FastAPI:
    captures_root, _, _ = _viewer_settings()
    app = FastAPI(title="Daylapse viewer", version="0.1.0")
    app.state.captures_root = captures_root

    static_dir = _HERE / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse, name="index")
    def index(request: Request) -> HTMLResponse:
        root: Path = app.state.captures_root
        days = list_recorded_days(root)
        return templates.TemplateResponse(
            request,
            "index.html",
            {"days": days, "captures_root": str(root)},
        )

    @app.get("/day/{day_iso}", response_class=HTMLResponse, name="day")
    def day_page(request: Request, day_iso: str) -> HTMLResponse:
        try:
            d = date.fromisoformat(day_iso)
        except ValueError as e:
            raise HTTPException(status_code=404, detail="Invalid date") from e
        root: Path = app.state.captures_root
        rec = get_day_record(root, d)
        if rec is None:
            raise HTTPException(status_code=404, detail="No recordings for this day")
        return templates.TemplateResponse(
            request,
            "day.html",
            {
                "rec": rec,
                "day_iso": d.isoformat(),
            },
        )

    @app.get(
        "/media/{day_iso}/{filename}",
        name="media",
    )
    def media(day_iso: str, filename: str) -> FileResponse:
        try:
            d = date.fromisoformat(day_iso)
        except ValueError as e:
            raise HTTPException(status_code=404, detail="Invalid date") from e
        root: Path = app.state.captures_root
        path = media_file_path(root, d, filename)
        if path is None:
            raise HTTPException(status_code=404, detail="Not found")
        mt = (
            "video/mp4"
            if filename.lower() == "summary.mp4"
            else "image/jpeg"
        )
        return FileResponse(path, media_type=mt, filename=filename)

    @app.get("/api/days", name="api_days")
    def api_days() -> list[dict[str, object]]:
        root: Path = app.state.captures_root
        out = []
        for r in list_recorded_days(root):
            out.append(
                {
                    "date": r.day.isoformat(),
                    "has_video": r.has_video,
                    "image_count": len(r.images),
                    "images": list(r.images),
                }
            )
        return out

    return app


app = create_app()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    import uvicorn

    root, host, port = _viewer_settings()
    logger.info("Starting viewer (captures=%s, http://%s:%s)", root, host, port)
    uvicorn.run(
        "daylapse.viewer.main:app",
        host=host,
        port=port,
        factory=False,
        log_level="info",
    )
