"""FastAPI app: list days, stream summary MP4, browse JPEG frames."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from daylapse.viewer.config import Settings
from daylapse.viewer.storage import get_day_record, list_recorded_days, media_file_path

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_HERE / "templates"))


def create_app() -> FastAPI:
    settings = Settings.from_env()
    app = FastAPI(title="Daylapse viewer", version="0.1.0")
    app.state.captures_root = settings.captures_root

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

    settings = Settings.from_env()
    root = settings.captures_root
    logger.info("Starting viewer (captures=%s, http://%s:%s)", root, settings.host, settings.port)
    uvicorn.run(
        "daylapse.viewer.main:app",
        host=settings.host,
        port=settings.port,
        factory=False,
        log_level="info",
    )
