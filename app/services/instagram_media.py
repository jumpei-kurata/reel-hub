import os
import re
from typing import Optional

import httpx

from app.config import FACEBOOK_PAGE_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID

_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_FIELDS = "id,shortcode,media_type,media_url,permalink,caption,thumbnail_url,timestamp,username"
_SHORTCODE_RE = re.compile(r"instagram\.com/(?:[^/?#]+/)?(?:p|reels?|tv)/([A-Za-z0-9_-]+)")
# 100件 × 20ページ = 直近2,000投稿まで遡る
_MAX_PAGES = 20


def extract_shortcode(url: str) -> Optional[str]:
    m = _SHORTCODE_RE.search(url)
    return m.group(1) if m else None


class OwnMediaNotFound(Exception):
    """自分の投稿に見つからなかった。メッセージに探した範囲を入れる。"""


class ManualDownloadNeeded(RuntimeError):
    """Instagram から自動では取れない投稿。画面は手で保存する手順 (外部の保存サイトを開くボタン) を出す。"""


async def find_own_media(shortcode: str) -> Optional[dict]:
    """自分の IG ビジネスアカウントの投稿から shortcode が一致するものを探す。

    Instagram はログインなしの取得(yt-dlp)を止めているため、自分の投稿は
    Graph API の media_url から直接受け取る。設定が無ければ None、
    探して見つからなければ OwnMediaNotFound。
    """
    if not FACEBOOK_PAGE_ACCESS_TOKEN or not INSTAGRAM_BUSINESS_ACCOUNT_ID:
        return None

    url = f"{_GRAPH_BASE}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
    params: Optional[dict] = {"fields": _FIELDS, "limit": 100, "access_token": FACEBOOK_PAGE_ACCESS_TOKEN}
    scanned = 0
    username = ""
    oldest = ""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for _ in range(_MAX_PAGES):
            data = (await client.get(url, params=params)).json()
            if "error" in data:
                err = data["error"]
                raise RuntimeError(err.get("message", str(err)) if isinstance(err, dict) else str(err))
            for media in data.get("data", []):
                if media.get("shortcode") == shortcode or f"/{shortcode}/" in (media.get("permalink") or ""):
                    return media
                scanned += 1
                username = username or media.get("username", "")
                oldest = (media.get("timestamp") or oldest)[:10]
            # paging.next には access_token 込みのクエリが入っている
            url = (data.get("paging") or {}).get("next")
            if not url:
                break
            params = None
    raise OwnMediaNotFound(f"@{username} の投稿 {scanned} 件（{oldest} まで）に見つかりませんでした")


async def download_own_media(media: dict, output_dir: str) -> dict:
    if media.get("media_type") != "VIDEO":
        raise RuntimeError("この投稿は動画ではありません（写真・複数枚の投稿には未対応です）")
    media_url = media.get("media_url")
    if not media_url:
        # Graph API は、著作権のある音源 (Instagram の音楽ライブラリの曲を含む) が入った動画や著作権で
        # flag された動画では、自分の投稿でも media_url を返さない (公式リファレンスの仕様)
        raise ManualDownloadNeeded(
            "この投稿は Instagram の音楽ライブラリの曲付きなどの理由で、Instagram が動画ファイルを渡しません"
            "（自分の投稿でも同じ）。下の「indown.io で取る」から保存して、アップロードしてください"
        )

    dest = os.path.join(output_dir, "video.mp4")
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        async with client.stream("GET", media_url) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)

    caption = media.get("caption") or ""
    return {"title": caption.split("\n", 1)[0][:80], "thumbnail": media.get("thumbnail_url", "")}
