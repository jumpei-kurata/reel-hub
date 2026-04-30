import httpx

from app.config import FACEBOOK_PAGE_ACCESS_TOKEN

_GRAPH_BASE = "https://graph.facebook.com/v19.0"


async def post_video(video_path: str, message: str) -> dict:
    data: dict = {
        "description": message,
        "published": "true",
        "access_token": FACEBOOK_PAGE_ACCESS_TOKEN,
    }

    async with httpx.AsyncClient(timeout=300) as client:
        with open(video_path, "rb") as f:
            resp = await client.post(
                f"{_GRAPH_BASE}/me/videos",
                data=data,
                files={"source": ("video.mp4", f, "video/mp4")},
            )

    if resp.status_code != 200:
        raise RuntimeError(f"Facebook API エラー: {resp.text}")

    return resp.json()
