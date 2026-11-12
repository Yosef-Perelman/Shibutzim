"""Serves the built client next to the API (plan 005, architecture §10).

One container, one origin: hashed assets are cached for a year, every other file and the index page
are always revalidated, and an address the client owns (`/me/shifts`) gets the index page so the
router can take over. A missing file or an unknown `/api` path stays a JSON 404.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

ASSETS_PREFIX = "assets/"
API_PREFIX = "api"
IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"


def mount_client(application: FastAPI, static_dir: Path) -> None:
    """Add the fallback route when `static_dir` holds a built client; otherwise do nothing."""
    root = static_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        return

    @application.get("/{path:path}", include_in_schema=False)
    def serve_client(path: str) -> FileResponse:
        if path == API_PREFIX or path.startswith(f"{API_PREFIX}/"):
            raise HTTPException(status_code=404)
        file = find_file(root, path)
        if file is not None:
            cache = IMMUTABLE if path.startswith(ASSETS_PREFIX) else REVALIDATE
            return FileResponse(file, headers={"Cache-Control": cache})
        if Path(path).suffix:  # a file that is not there, not an address of the client
            raise HTTPException(status_code=404)
        return FileResponse(index, headers={"Cache-Control": REVALIDATE})


def find_file(root: Path, path: str) -> Path | None:
    """The file under `root` that `path` names, or None; never anything outside `root`."""
    try:
        candidate = (root / path).resolve()
    except (OSError, ValueError):
        return None
    if candidate.is_file() and candidate.is_relative_to(root):
        return candidate
    return None
