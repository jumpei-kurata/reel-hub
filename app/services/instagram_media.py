import os
import re
from typing import Optional

import httpx

from app.config import FACEBOOK_PAGE_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID

_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_FIELDS = "id,shortcode,media_type,media_url,permalink,caption,thumbnail_url"
_SHORTCODE_RE = re.compile(r"instagram\.com/(?:[^/?#]+/)?(?:p|reels?|tv)/([A-Za-z0-9_-]+)")
# 100件 × 20ページ = 直近2,000投稿まで遡る
_MAX_PAGES = 20


def extract_shortcode(url: str) -> Optional[str]:
    m = _SHORTCODE_RE.search(url)
    return m.group(1) if m else None


async def find_own_media(shortcode: str) -> Optional[dict]:
    """自分の IG ビジネスアカウントの投稿から shortcode が一致するものを探す。

    Instagram はログインなしの取得(yt-dlp)を止めているため、自分の投稿は
    Graph API の media_url から直接受け取る。見つからなければ None。
    """
    if not FACEBOOK_PAGE_ACCESS_TOKEN or not INSTAGRAM_BUSINESS_ACCOUNT_ID:
        return None

    url = f"{_GRAPH_BASE}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
    params: Optional[dict] = {"fields": _FIELDS, "limit": 100, "access_token": FACEBOOK_PAGE_ACCESS_TOKEN}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for _ in range(_MAX_PAGES):
            data = (await client.get(url, params=params)).json()
            if "error" in data:
                err = data["error"]
                raise RuntimeError(err.get("message", str(err)) if isinstance(err, dict) else str(err))
            for media in data.get("data", []):
                if media.get("shortcode") == shortcode or f"/{shortcode}/" in (media.get("permalink") or ""):
                    return media
            # paging.next には access_token 込みのクエリが入っている
            url = (data.get("paging") or {}).get("next")
            if not url:
                return None
            params = None
    return None


async def download_own_media(media: dict, output_dir: str) -> dict:
    if media.get("media_type") != "VIDEO":
        raise RuntimeError("この投稿は動画ではありません（写真・複数枚の投稿には未対応です）")
    media_url = media.get("media_url")
    if not media_url:
        # 音源の著作権などで Instagram が動画ファイルを渡さない投稿がある
        raise RuntimeError("Instagram がこの投稿の動画ファイルを渡してくれませんでした。カメラロールの元動画をアップロードしてください")

    dest = os.path.join(output_dir, "video.mp4")
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        async with client.stream("GET", media_url) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)

    caption = media.get("caption") or ""
    return {"title": caption.split("\n", 1)[0][:80], "thumbnail": media.get("thumbnail_url", "")}
