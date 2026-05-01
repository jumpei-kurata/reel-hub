import asyncio

import httpx

from app.config import APP_BASE_URL, FACEBOOK_PAGE_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID

_GRAPH_BASE = "https://graph.facebook.com/v19.0"


async def post_reel(video_id: str, caption: str) -> dict:
    token = FACEBOOK_PAGE_ACCESS_TOKEN
    ig_id = INSTAGRAM_BUSINESS_ACCOUNT_ID
    video_url = f"{APP_BASE_URL}/api/video/{video_id}"

    # 各HTTPリクエストに30秒タイムアウト（ポーリングのsleepは含まれない）
    request_timeout = httpx.Timeout(30.0)

    async with httpx.AsyncClient() as client:
        # Step 1: メディアコンテナ作成（InstagramがURLから動画を取得）
        resp = await client.post(
            f"{_GRAPH_BASE}/{ig_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": token,
            },
            timeout=request_timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Instagram container エラー: {resp.text}")
        container_id = resp.json()["id"]

        # Step 2: 動画処理完了を待機（最大2分）
        for _ in range(24):
            await asyncio.sleep(5)
            status_resp = await client.get(
                f"{_GRAPH_BASE}/{container_id}",
                params={"fields": "status_code,status", "access_token": token},
                timeout=request_timeout,
            )
            status_code = status_resp.json().get("status_code", "")
            if status_code == "FINISHED":
                break
            if status_code == "ERROR":
                raise RuntimeError(f"Instagram 動画処理エラー: {status_resp.text}")
        else:
            raise RuntimeError("Instagram 動画処理タイムアウト（2分）")

        # Step 3: 公開
        pub_resp = await client.post(
            f"{_GRAPH_BASE}/{ig_id}/media_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=request_timeout,
        )
        if pub_resp.status_code != 200:
            raise RuntimeError(f"Instagram 公開エラー: {pub_resp.text}")

        return pub_resp.json()
