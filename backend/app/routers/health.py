from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health():
    # Deliberately NOT rate-limited. This is the availability probe for the
    # panel (polled every few seconds per install) and for railway.json's
    # platform healthcheck, and its load scales with the number of installed
    # users while a rate-limit identity is the shared public IP - three users
    # behind one carrier NAT tripped the old 30/minute bucket in the field
    # (2026-10-30). Any per-identity number fails at some N. The endpoint is
    # an O(1) static response with no I/O: none of the resources the limiter
    # protects (AI spend, Tavily credits, the event loop under model work)
    # are touched here. A flood of it is an edge/infra concern, not an
    # application one. Pinned by
    # tests/test_rate_limit_policy.py::test_health_carries_no_per_identity_rate_limit.
    return JSONResponse({"status": "ok"})
