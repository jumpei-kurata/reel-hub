import math
import os

import httpx

_API_BASE = "https://open.tiktokapis.com/v2"
_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB


async def post_video(video_path: str, caption: str, access_token: str) -> dict:
    file_size = os.path.getsize(video_path)
    chunk_size = _CHUNK_SIZE if file_size > _CHUNK_SIZE else file_size
    total_chunks = math.ceil(file_size / chunk_size)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    async with httpx.AsyncClient(timeout=300) as client:
        init_resp = await client.post(
            f"{_API_BASE}/post/publish/video/init/",
            headers=headers,
            json={
                "post_info": {
                    "title": caption[:150],
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": chunk_size,
                    "total_chunk_count": total_chunks,
                },
            },
        )

        if init_resp.status_code != 200:
            raise RuntimeError(f"TikTok init エラー: {init_resp.text}")

        data = init_resp.json()["data"]
        publish_id = data["publish_id"]
        upload_url = data["upload_url"]

        with open(video_path, "rb") as f:
            for i in range(total_chunks):
                chunk = f.read(chunk_size)
                start = i * chunk_size
                end = start + len(chunk) - 1
                upload_resp = await client.put(
                    upload_url,
                    content=chunk,
                    headers={
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Content-Type": "video/mp4",
                        "Content-Length": str(len(chunk)),
                    },
                )
                if upload_resp.status_code not in (200, 201, 206):
                    raise RuntimeError(f"TikTok upload エラー: {upload_resp.text}")

    return {"publish_id": publish_id}


async def exchange_code_for_tokens(code: str, redirect_uri: str, client_key: str, client_secret: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_API_BASE}/oauth/token/",
            data={
                "client_key": client_key,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code != 200:
        raise RuntimeError(f"TikTok token エラー: {resp.text}")
    return resp.json()


async def refresh_access_token(refresh_token: str, client_key: str, client_secret: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_API_BASE}/oauth/token/",
            data={
                "client_key": client_key,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code != 200:
        raise RuntimeError(f"TikTok refresh エラー: {resp.text}")
    return resp.json()
