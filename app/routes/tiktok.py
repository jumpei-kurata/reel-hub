import json
import os
import re
import secrets

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.config import APP_BASE_URL, TIKTOK_ACCESS_TOKEN, TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET
from app.services.downloader import get_video_path
from app.services.tiktok import exchange_code_for_tokens, post_video, refresh_access_token

router = APIRouter()

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_TOKEN_FILE = "/tmp/reel-hub/tiktok_tokens.json"


def _load_tokens() -> tuple[str, str]:
    try:
        with open(_TOKEN_FILE) as f:
            d = json.load(f)
            return d.get("access_token", ""), d.get("refresh_token", "")
    except Exception:
        return "", ""


def _save_tokens(access_token: str, refresh_token: str) -> None:
    os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
    with open(_TOKEN_FILE, "w") as f:
        json.dump({"access_token": access_token, "refresh_token": refresh_token}, f)


# Seed from env, then try file
_access_token = TIKTOK_ACCESS_TOKEN
_refresh_token = ""
if not _access_token:
    _access_token, _refresh_token = _load_tokens()

_pending_states: set[str] = set()


class TikTokPostRequest(BaseModel):
    video_id: str
    caption: str


@router.post("/api/tiktok/post")
async def post_to_tiktok(req: TikTokPostRequest):
    global _access_token, _refresh_token
    if not _access_token:
        raise HTTPException(status_code=503, detail="TikTokが認証されていません。/auth/tiktok を開いてください")
    if not _UUID_RE.match(req.video_id):
        raise HTTPException(status_code=400, detail="Invalid video ID")
    try:
        path = get_video_path(req.video_id)
        return await post_video(path, req.caption, _access_token)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="動画が見つかりません")
    except RuntimeError as e:
        # トークン失効時に自動リフレッシュして1回リトライ
        if "token" in str(e).lower() or "auth" in str(e).lower() or "access_token" in str(e).lower():
            if _refresh_token and TIKTOK_CLIENT_KEY:
                try:
                    data = await refresh_access_token(_refresh_token, TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET)
                    _access_token = data.get("access_token", "")
                    _refresh_token = data.get("refresh_token", _refresh_token)
                    _save_tokens(_access_token, _refresh_token)
                    path = get_video_path(req.video_id)
                    return await post_video(path, req.caption, _access_token)
                except Exception as e2:
                    raise HTTPException(status_code=500, detail=f"トークン更新失敗: {e2}")
        raise HTTPException(status_code=500, detail=str(e))
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
    global _access_token, _refresh_token
    if state not in _pending_states:
        raise HTTPException(status_code=400, detail="Invalid state")
    _pending_states.discard(state)

    redirect_uri = f"{APP_BASE_URL}/auth/tiktok/callback"
    data = await exchange_code_for_tokens(code, redirect_uri, TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET)
    _access_token = data.get("access_token", "")
    _refresh_token = data.get("refresh_token", "")

    _save_tokens(_access_token, _refresh_token)

    return HTMLResponse("""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{font-family:-apple-system,sans-serif;background:#0d0d0d;color:#fff;padding:24px;max-width:500px;margin:0 auto;text-align:center;padding-top:60px}
  h2{color:#00b894;margin-bottom:16px}
  p{color:#aaa;font-size:14px}
</style></head><body>
<h2>✅ TikTok認証完了</h2>
<p>このタブを閉じています...</p>
<script>
  if (window.opener) {
    try { window.opener.checkStatus(); } catch(e) {}
    window.close();
  } else {
    window.location.href = '/';
  }
</script>
</body></html>""")


@router.get("/auth/status")
async def auth_status():
    return {
        "facebook_configured": bool(os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")),
        "tiktok_configured": bool(_access_token),
        "instagram_configured": bool(os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")),
    }
