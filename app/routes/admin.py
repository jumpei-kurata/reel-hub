import secrets

from fastapi import APIRouter, HTTPException, Query

from app.config import REFRESH_SECRET
from app.services.token_refresh import refresh_facebook_token

router = APIRouter()


@router.post("/api/refresh-token")
async def refresh_token(secret: str = Query(...)):
    if not REFRESH_SECRET or not secrets.compare_digest(secret, REFRESH_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    result = await refresh_facebook_token()
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
