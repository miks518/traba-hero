from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.rate_limit import limiter

router = APIRouter()


@router.get("/health")
@limiter.limit("30/minute")
async def health(request: Request):
    return JSONResponse({"status": "ok"})
