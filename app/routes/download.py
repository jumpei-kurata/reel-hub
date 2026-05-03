import os
import re
import shutil
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import DOWNLOAD_DIR
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


_MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500MB


@router.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    from app.services.transcoder import to_h264_mp4

    ext = os.path.splitext(file.filename or "")[1].lower() or ".mp4"
    if ext not in (".mp4", ".mov", ".m4v"):
        raise HTTPException(status_code=400, detail="mp4 / mov のみ対応しています")

    video_id = str(uuid.uuid4())
    output_dir = os.path.join(DOWNLOAD_DIR, video_id)
    os.makedirs(output_dir, exist_ok=True)

    raw_path = os.path.join(output_dir, f"raw{ext}")
    size = 0
    with open(raw_path, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > _MAX_UPLOAD_BYTES:
                os.remove(raw_path)
                raise HTTPException(status_code=413, detail="ファイルが大きすぎます（500MB以下にしてください）")
            f.write(chunk)

    mp4_path = os.path.join(output_dir, "video.mp4")
    await to_h264_mp4(raw_path, mp4_path)
    os.remove(raw_path)

    return {"video_id": video_id}


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
