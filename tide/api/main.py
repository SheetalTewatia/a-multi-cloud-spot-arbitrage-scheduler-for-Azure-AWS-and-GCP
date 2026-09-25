"""FastAPI app. Workload submission, decisions and savings endpoints arrive in later phases."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from tide import __version__, db

app = FastAPI(title="Tide", version=__version__)


@app.get("/health")
def health() -> JSONResponse:
    """Liveness + database check. Returns 503 if Postgres is unreachable."""
    if db.check_connection():
        return JSONResponse({"status": "ok", "db": "ok"})
    return JSONResponse({"status": "degraded", "db": "unreachable"}, status_code=503)
