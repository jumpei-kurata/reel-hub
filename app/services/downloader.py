import asyncio
import glob
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import yt_dlp

from app.config import DOWNLOAD_DIR
from app.services.instagram_media import OwnMediaNotFound, download_own_media, extract_shortcode, find_own_media

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

    # 自分の投稿は Graph API から受け取る（yt-dlp はログインなしだと Instagram に弾かれる）
    shortcode = extract_shortcode(url)
    own_error = None
    media = None
    if shortcode:
        try:
            media = await find_own_media(shortcode)
        except OwnMediaNotFound as e:
            own_error = str(e)
        except Exception as e:
            own_error = f"自分の投稿の検索でエラー: {e}"
    if media:
        info = await download_own_media(media, output_dir)
    else:
        loop = asyncio.get_event_loop()
        try:
            info = await loop.run_in_executor(_executor, _download_sync, url, output_dir)
        except Exception as e:
            if not shortcode:
                raise
            reason = own_error or "自分の投稿を探す設定がありません"
            raise RuntimeError(f"取れませんでした（{reason}）。他人の投稿は Instagram がログインなしの取得を止めています") from e

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
