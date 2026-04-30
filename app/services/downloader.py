import asyncio
import glob
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import yt_dlp

from app.config import DOWNLOAD_DIR

_executor = ThreadPoolExecutor(max_workers=2)


def _download_sync(url: str, output_dir: str) -> dict:
    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(output_dir, "video.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    return {"title": info.get("title", ""), "thumbnail": info.get("thumbnail", "")}


async def download_video(url: str) -> dict:
    video_id = str(uuid.uuid4())
    output_dir = os.path.join(DOWNLOAD_DIR, video_id)
    os.makedirs(output_dir, exist_ok=True)

    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(_executor, _download_sync, url, output_dir)

    files = glob.glob(os.path.join(output_dir, "*"))
    if not files:
        raise RuntimeError("ダウンロードに失敗しました")

    return {"video_id": video_id, "video_path": files[0], **info}


def get_video_path(video_id: str) -> str:
    video_dir = os.path.join(DOWNLOAD_DIR, video_id)
    files = glob.glob(os.path.join(video_dir, "*"))
    if not files:
        raise FileNotFoundError("動画が見つかりません")
    return files[0]
