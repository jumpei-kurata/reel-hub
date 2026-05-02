import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import FACEBOOK_PAGE_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID
from app.services.instagram import post_reel

router = APIRouter()

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class InstagramPostRequest(BaseModel):
    video_id: str
    caption: str


@router.post("/api/instagram/post")
async def post_to_instagram(req: InstagramPostRequest):
    if not FACEBOOK_PAGE_ACCESS_TOKEN or not INSTAGRAM_BUSINESS_ACCOUNT_ID:
        raise HTTPException(status_code=503, detail="Instagramが設定されていません（INSTAGRAM_BUSINESS_ACCOUNT_IDを確認）")
    if not _UUID_RE.match(req.video_id):
        raise HTTPException(status_code=400, detail="Invalid video ID")
    try:
        return await post_reel(req.video_id, req.caption)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/instagram/process-comments")
async def process_instagram_comments():
    if not FACEBOOK_PAGE_ACCESS_TOKEN or not INSTAGRAM_BUSINESS_ACCOUNT_ID:
        raise HTTPException(status_code=503, detail="Instagramが設定されていません")
    try:
        from app.services.instagram_comments import process_comments
        return await process_comments()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
