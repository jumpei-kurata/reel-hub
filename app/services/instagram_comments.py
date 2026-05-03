import json
import unicodedata
from pathlib import Path

import httpx

from app.config import DOWNLOAD_DIR, FACEBOOK_PAGE_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID

_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_PROCESSED_FILE = Path(DOWNLOAD_DIR) / "processed_comments.json"
_REPLY_TEXT = "🔥🔥🔥"


def _load_processed() -> set[str]:
    try:
        return set(json.loads(_PROCESSED_FILE.read_text()))
    except Exception:
        return set()


def _save_processed(ids: set[str]) -> None:
    _PROCESSED_FILE.write_text(json.dumps(list(ids)))


def is_emoji_only(text: str) -> bool:
    """アルファベット・数字・CJK文字を含まない（絵文字・記号のみ）かどうか判定"""
    text = text.strip()
    if not text:
        return False
    for char in text:
        if char.isspace():
            continue
        cat = unicodedata.category(char)
        if cat.startswith("L") or cat.startswith("N"):
            return False
    return True


async def _already_replied(client: httpx.AsyncClient, comment_id: str, token: str) -> bool:
    """自分がすでに🔥🔥🔥で返信済みかどうか確認（サーバー再起動後の重複返信防止）"""
    resp = await client.get(
        f"{_GRAPH_BASE}/{comment_id}/replies",
        params={"fields": "text", "access_token": token},
    )
    data = resp.json()
    return any(r.get("text") == _REPLY_TEXT for r in data.get("data", []))


async def process_comments() -> dict:
    token = FACEBOOK_PAGE_ACCESS_TOKEN
    ig_id = INSTAGRAM_BUSINESS_ACCOUNT_ID
    processed = _load_processed()
    liked = 0
    replied = 0
    errors = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        media_resp = await client.get(
            f"{_GRAPH_BASE}/{ig_id}/media",
            params={"fields": "id", "limit": 10, "access_token": token},
        )
        media_data = media_resp.json()
        if "error" in media_data:
            return {"error": media_data["error"]["message"]}

        for media in media_data.get("data", []):
            media_id = media["id"]

            comments_resp = await client.get(
                f"{_GRAPH_BASE}/{media_id}/comments",
                params={"fields": "id,text,timestamp", "access_token": token},
            )
            comments_data = comments_resp.json()
            if "error" in comments_data:
                errors.append(f"media {media_id}: {comments_data['error']['message']}")
                continue

            for comment in comments_data.get("data", []):
                cid = comment["id"]
                text = comment.get("text", "")

                # いいね（processed済みでもidempotentなので毎回試みる）
                if cid not in processed:
                    try:
                        await client.post(
                            f"{_GRAPH_BASE}/{cid}/likes",
                            data={"access_token": token},
                        )
                        liked += 1
                    except Exception as e:
                        errors.append(f"like {cid}: {e}")

                # 絵文字のみなら返信（APIで重複チェック）
                if is_emoji_only(text):
                    try:
                        if not await _already_replied(client, cid, token):
                            await client.post(
                                f"{_GRAPH_BASE}/{cid}/replies",
                                data={"message": _REPLY_TEXT, "access_token": token},
                            )
                            replied += 1
                    except Exception as e:
                        errors.append(f"reply {cid}: {e}")

                processed.add(cid)

    _save_processed(processed)
    return {"liked": liked, "replied": replied, "errors": errors}
