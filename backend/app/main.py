import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.routers import health, scan
from app.exceptions import AppError, app_error_handler
from app.rate_limit import limiter
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("trabahero")

app = FastAPI(title="Trabahero Backend")


class DropHealthAccessLogs(logging.Filter):
    """Silences uvicorn access records for GET /health.

    The extension polls /health every few seconds to detect reachability, which
    would otherwise bury real requests in the log. Any other path is untouched.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple):
            for arg in args:
                if isinstance(arg, str) and arg.split("?", 1)[0] == "/health":
                    return False
        return True


logging.getLogger("uvicorn.access").addFilter(DropHealthAccessLogs())

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)

app.include_router(health.router)
app.include_router(scan.router)


def run(reload: bool = False) -> None:
    """Serve the API on the host and port from `backend/.env`.

    Exists because `uvicorn app.main:app` does **not** read them. Uvicorn takes
    its own port from the command line and defaults to 8000, so a `PORT` in the
    env file that nothing reads leaves the server on 8000 while the file says
    otherwise — and the only symptom is a port mismatch nobody can explain.
    That is why HOST and PORT were previously decorative.

    Use this, not bare uvicorn, unless you pass `--port` yourself:

        python -m app.main                    # honours HOST and PORT
        uvicorn app.main:app --reload --port 8010   # same thing, explicit

    `reload` is a development convenience. It is a parameter rather than a
    setting so a deployment cannot pick it up from the environment by accident.
    """
    uvicorn.run(app, host=settings.host, port=settings.port, reload=reload)


if __name__ == "__main__":
    run(reload=True)
