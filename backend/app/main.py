import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.routers import health, scan
from app.exceptions import AppError, app_error_handler
from app.rate_limit import limiter

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
