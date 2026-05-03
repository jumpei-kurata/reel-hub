import os

import httpx

from app.config import FACEBOOK_PAGE_ACCESS_TOKEN

_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_CHUNK_SIZE = 50 * 1024 * 1024  # 50MB


async def post_video(video_path: str, message: str) -> dict:
    token = FACEBOOK_PAGE_ACCESS_TOKEN
    file_size = os.path.getsize(video_path)

    async with httpx.AsyncClient(timeout=300.0) as client:
        # Phase 1: アップロードセッション開始
        start_resp = await client.post(
            f"{_GRAPH_BASE}/me/videos",
            data={
                "upload_phase": "start",
                "file_size": str(file_size),
                "access_token": token,
            },
        )
        if start_resp.status_code != 200:
            raise RuntimeError(f"Facebook API エラー: [{start_resp.status_code}] {start_resp.text}")

        session_id = start_resp.json()["upload_session_id"]

        # Phase 2: チャンク分割アップロード
        with open(video_path, "rb") as f:
            start_offset = 0
            while start_offset < file_size:
                chunk = f.read(_CHUNK_SIZE)
                if not chunk:
                    break
                transfer_resp = await client.post(
                    f"{_GRAPH_BASE}/me/videos",
                    data={
                        "upload_phase": "transfer",
                        "upload_session_id": session_id,
                        "start_offset": str(start_offset),
                        "access_token": token,
                    },
                    files={"video_file_chunk": ("chunk", chunk, "application/octet-stream")},
                )
                if transfer_resp.status_code != 200:
                    raise RuntimeError(f"Facebook upload エラー: [{transfer_resp.status_code}] {transfer_resp.text}")
                start_offset = int(transfer_resp.json()["start_offset"])

        # Phase 3: 公開
        finish_resp = await client.post(
            f"{_GRAPH_BASE}/me/videos",
            data={
                "upload_phase": "finish",
                "upload_session_id": session_id,
                "description": message,
                "published": "true",
                "access_token": token,
            },
        )
        if finish_resp.status_code != 200:
            raise RuntimeError(f"Facebook publish エラー: [{finish_resp.status_code}] {finish_resp.text}")

        return finish_resp.json()
