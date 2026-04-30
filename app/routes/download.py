import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.downloader import download_video, get_video_path

router = APIRouter()

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class DownloadRequest(BaseModel):
    url: str


@router.post("/download")
async def download(req: DownloadRequest):
    try:
        return await download_video(req.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/video/{video_id}")
async def serve_video(video_id: str, download: bool = False):
    if not _UUID_RE.match(video_id):
        raise HTTPException(status_code=400, detail="Invalid video ID")
    try:
        path = get_video_path(video_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="動画が見つかりません")

    headers = {}
    if download:
        headers["Content-Disposition"] = "attachment; filename=video.mp4"
    return FileResponse(path, media_type="video/mp4", headers=headers)
