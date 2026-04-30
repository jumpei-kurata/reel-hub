import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import FACEBOOK_PAGE_ACCESS_TOKEN
from app.services.downloader import get_video_path
from app.services.facebook import post_video

router = APIRouter()

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class FacebookPostRequest(BaseModel):
    video_id: str
    message: str
    published: bool = True


@router.post("/facebook/post")
async def post_to_facebook(req: FacebookPostRequest):
    if not FACEBOOK_PAGE_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail="Facebookが設定されていません")
    if not _UUID_RE.match(req.video_id):
        raise HTTPException(status_code=400, detail="Invalid video ID")
    try:
        path = get_video_path(req.video_id)
        return await post_video(path, req.message, req.published)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="動画が見つかりません")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
