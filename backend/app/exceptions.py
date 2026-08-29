from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 500
    detail = "Internal server error"


class InvalidImageError(AppError):
    status_code = 400
    detail = "Invalid or missing image data"


class AIServiceError(AppError):
    status_code = 502
    detail = "AI service call failed"


async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
