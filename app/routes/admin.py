import secrets

from fastapi import APIRouter, HTTPException, Query

from app.config import REFRESH_SECRET
from app.services.instagram_insights import get_recent_insights
from app.services.token_refresh import refresh_facebook_token

router = APIRouter()


def _check_secret(secret: str) -> None:
    if not REFRESH_SECRET or not secrets.compare_digest(secret, REFRESH_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/api/refresh-token")
async def refresh_token(secret: str = Query(...)):
    _check_secret(secret)
    result = await refresh_facebook_token()
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/api/insights")
async def insights(secret: str = Query(...), limit: int = Query(10, ge=1, le=25)):
    _check_secret(secret)
    result = await get_recent_insights(limit=limit)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
