import os

import httpx

from app.config import FACEBOOK_PAGE_ACCESS_TOKEN, FACEBOOK_PAGE_ID

_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_CHUNK_SIZE = 50 * 1024 * 1024  # 50MB

_page_token_cache: dict[str, str] = {}


def _is_token_error(resp: httpx.Response) -> bool:
    try:
        err = resp.json().get("error", {})
    except Exception:
        return False
    return err.get("type") == "OAuthException" or err.get("code") in {102, 190, 463, 467}


async def _get_page_access_token(client: httpx.AsyncClient, user_token: str, page_id: str) -> str:
    if page_id in _page_token_cache:
        return _page_token_cache[page_id]

    # /me/accounts（クラシックPage向け）。新フォーマット Business Portfolio Page は出ないことがある
    r = await client.get(
        f"{_GRAPH_BASE}/me/accounts",
        params={"fields": "id,access_token", "access_token": user_token},
    )
    if r.status_code != 200:
        raise RuntimeError(f"Facebook /me/accounts エラー: [{r.status_code}] {r.text}")
    for page in r.json().get("data", []):
        if page.get("id") == page_id:
            token = page.get("access_token")
            if not token:
                raise RuntimeError(f"Page {page_id} に access_token が含まれていません")
            _page_token_cache[page_id] = token
            return token

    # フォールバック: Page を直接叩いて access_token を取得（新フォーマットPage対策）
    r2 = await client.get(
        f"{_GRAPH_BASE}/{page_id}",
        params={"fields": "access_token", "access_token": user_token},
    )
    if r2.status_code == 200:
        token = r2.json().get("access_token")
        if token:
            _page_token_cache[page_id] = token
            return token

    raise RuntimeError(
        f"ユーザートークンから Page {page_id} のトークンを取得できませんでした "
        f"(/me/accounts に未含・/{page_id} fallback も失敗 [{r2.status_code}] {r2.text[:200]})"
    )


async def post_video(video_path: str, message: str) -> dict:
    user_token = FACEBOOK_PAGE_ACCESS_TOKEN
    if not FACEBOOK_PAGE_ID:
        raise RuntimeError("FACEBOOK_PAGE_ID 環境変数が未設定です")
    file_size = os.path.getsize(video_path)

    async with httpx.AsyncClient(timeout=300.0) as client:
        videos_url = f"{_GRAPH_BASE}/{FACEBOOK_PAGE_ID}/videos"

        async def _start_session(token: str):
            return await client.post(
                videos_url,
                data={
                    "upload_phase": "start",
                    "file_size": str(file_size),
                    "access_token": token,
                },
            )

        # Phase 1: アップロードセッション開始（キャッシュPageトークン失効に備えて、トークン関連エラー時のみ1回リトライ）
        was_cached = FACEBOOK_PAGE_ID in _page_token_cache
        page_token = await _get_page_access_token(client, user_token, FACEBOOK_PAGE_ID)
        start_resp = await _start_session(page_token)
        if start_resp.status_code != 200 and was_cached and _is_token_error(start_resp):
            _page_token_cache.pop(FACEBOOK_PAGE_ID, None)
            page_token = await _get_page_access_token(client, user_token, FACEBOOK_PAGE_ID)
            start_resp = await _start_session(page_token)
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
                    videos_url,
                    data={
                        "upload_phase": "transfer",
                        "upload_session_id": session_id,
                        "start_offset": str(start_offset),
                        "access_token": page_token,
                    },
                    files={"video_file_chunk": ("chunk", chunk, "application/octet-stream")},
                )
                if transfer_resp.status_code != 200:
                    raise RuntimeError(f"Facebook upload エラー: [{transfer_resp.status_code}] {transfer_resp.text}")
                start_offset = int(transfer_resp.json()["start_offset"])

        # Phase 3: 公開
        finish_resp = await client.post(
            videos_url,
            data={
                "upload_phase": "finish",
                "upload_session_id": session_id,
                "description": message,
                "published": "true",
                "access_token": page_token,
            },
        )
        if finish_resp.status_code != 200:
            raise RuntimeError(f"Facebook publish エラー: [{finish_resp.status_code}] {finish_resp.text}")

        return finish_resp.json()
