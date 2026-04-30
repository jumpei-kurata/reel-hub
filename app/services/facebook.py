import httpx

from app.config import FACEBOOK_PAGE_ACCESS_TOKEN, FACEBOOK_PAGE_ID

_GRAPH_BASE = "https://graph.facebook.com/v19.0"


async def post_video(video_path: str, message: str, published: bool = True) -> dict:
    data: dict = {
        "description": message,
        "published": str(published).lower(),
        "access_token": FACEBOOK_PAGE_ACCESS_TOKEN,
    }
    if not published:
        data["unpublished_content_type"] = "DRAFT"

    async with httpx.AsyncClient(timeout=300) as client:
        with open(video_path, "rb") as f:
            resp = await client.post(
                f"{_GRAPH_BASE}/{FACEBOOK_PAGE_ID}/videos",
                data=data,
                files={"source": ("video.mp4", f, "video/mp4")},
            )

    if resp.status_code != 200:
        raise RuntimeError(f"Facebook API エラー: {resp.text}")

    return resp.json()
