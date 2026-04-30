import os
import re
import secrets

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.config import APP_BASE_URL, TIKTOK_ACCESS_TOKEN, TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET
from app.services.downloader import get_video_path
from app.services.tiktok import exchange_code_for_tokens, post_video

router = APIRouter()

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# In-memory token store (seeded from env on startup)
_access_token = TIKTOK_ACCESS_TOKEN
_pending_states: set[str] = set()


class TikTokPostRequest(BaseModel):
    video_id: str
    caption: str


@router.post("/api/tiktok/post")
async def post_to_tiktok(req: TikTokPostRequest):
    if not _access_token:
        raise HTTPException(status_code=503, detail="TikTokが認証されていません。/auth/tiktok を開いてください")
    if not _UUID_RE.match(req.video_id):
        raise HTTPException(status_code=400, detail="Invalid video ID")
    try:
        path = get_video_path(req.video_id)
        return await post_video(path, req.caption, _access_token)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="動画が見つかりません")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/tiktok")
async def tiktok_auth():
    if not TIKTOK_CLIENT_KEY:
        raise HTTPException(status_code=503, detail="TIKTOK_CLIENT_KEY が設定されていません")
    state = secrets.token_urlsafe(16)
    _pending_states.add(state)
    redirect_uri = f"{APP_BASE_URL}/auth/tiktok/callback"
    url = (
        "https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={TIKTOK_CLIENT_KEY}"
        "&scope=video.publish,video.upload"
        "&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )
    return RedirectResponse(url)


@router.get("/auth/tiktok/callback")
async def tiktok_callback(code: str, state: str):
    global _access_token
    if state not in _pending_states:
        raise HTTPException(status_code=400, detail="Invalid state")
    _pending_states.discard(state)

    redirect_uri = f"{APP_BASE_URL}/auth/tiktok/callback"
    data = await exchange_code_for_tokens(code, redirect_uri, TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET)
    _access_token = data.get("access_token", "")
    refresh_token = data.get("refresh_token", "")

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{{font-family:-apple-system,sans-serif;background:#0d0d0d;color:#fff;padding:24px;max-width:500px;margin:0 auto}}
  h2{{color:#00b894;margin-bottom:16px}}
  pre{{background:#1a1a1a;border:1px solid #333;border-radius:8px;padding:12px;font-size:12px;overflow-x:auto;word-break:break-all;white-space:pre-wrap}}
  a{{color:#6c5ce7;display:inline-block;margin-top:20px;font-size:16px}}
</style></head><body>
<h2>✅ TikTok認証完了</h2>
<p>Renderの環境変数に以下を設定してください:</p>
<pre>TIKTOK_ACCESS_TOKEN={_access_token}
TIKTOK_REFRESH_TOKEN={refresh_token}</pre>
<a href="/">← ホームへ戻る</a>
</body></html>""")


@router.get("/auth/status")
async def auth_status():
    return {
        "facebook_configured": bool(os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")),
        "tiktok_configured": bool(_access_token),
    }
