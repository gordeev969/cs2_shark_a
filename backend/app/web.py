"""Serve the built React app when frontend and API share one hosted container."""

from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "API endpoint not found")
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or "." in Path(path).name:
                raise
            return await super().get_response("index.html", scope)
