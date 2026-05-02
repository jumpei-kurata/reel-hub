import re

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import FACEBOOK_PAGE_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID
from app.services.instagram import post_reel

router = APIRouter()

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_KNOWN_PAGE_ID = "975447125643031"


@router.get("/api/debug/ig-account-id")
async def debug_ig_account_id():
    """一時デバッグ用: 設定済みFBトークンでInstagram Business Account IDを取得する"""
    if not FACEBOOK_PAGE_ACCESS_TOKEN:
        return {"error": "FACEBOOK_PAGE_ACCESS_TOKEN not configured"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        page_resp = await client.get(
            f"{_GRAPH_BASE}/{_KNOWN_PAGE_ID}",
            params={"fields": "id,name,instagram_business_account", "access_token": FACEBOOK_PAGE_ACCESS_TOKEN},
        )
        page_data = page_resp.json()

        accounts_resp = await client.get(
            f"{_GRAPH_BASE}/me/accounts",
            params={"fields": "id,name,instagram_business_account", "access_token": FACEBOOK_PAGE_ACCESS_TOKEN},
        )
        accounts_data = accounts_resp.json()

    return {
        "page_direct": page_data,
        "me_accounts": accounts_data,
        "hint": "page_direct の instagram_business_account.id が INSTAGRAM_BUSINESS_ACCOUNT_ID に設定する値",
    }


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
