import json
import time
import unicodedata
from pathlib import Path

import httpx

from app.config import DOWNLOAD_DIR, FACEBOOK_PAGE_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID

_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_PROCESSED_FILE = Path(DOWNLOAD_DIR) / "processed_comments.json"
_REPLY_TEXT = "🔥🔥🔥"
_TTL_SECONDS = 30 * 24 * 60 * 60  # 30日


def _load_processed() -> dict[str, float]:
    try:
        data = json.loads(_PROCESSED_FILE.read_text())
        if not isinstance(data, dict):
            # 旧フォーマット（list）からの移行: 現在時刻で引き継ぐ
            now = time.time()
            data = {k: now for k in data}
        cutoff = time.time() - _TTL_SECONDS
        return {k: v for k, v in data.items() if v > cutoff}
    except Exception:
        return {}


def _save_processed(ids: dict[str, float]) -> None:
    _PROCESSED_FILE.write_text(json.dumps(ids))


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
                params={"fields": "id,text,timestamp,from", "access_token": token},
            )
            comments_data = comments_resp.json()
            if "error" in comments_data:
                errors.append(f"media {media_id}: {comments_data['error']['message']}")
                continue

            for comment in comments_data.get("data", []):
                cid = comment["id"]

                if cid not in processed:
                    # 自分のコメントはスキップ（いいね・返信しない）
                    if comment.get("from", {}).get("id") == ig_id:
                        processed[cid] = time.time()
                    else:
                        text = comment.get("text", "")

                        # いいね
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

                        processed[cid] = time.time()

                # 返信を処理（常に取得して新しい返信を見逃さない）
                try:
                    replies_resp = await client.get(
                        f"{_GRAPH_BASE}/{cid}/replies",
                        params={"fields": "id,from", "access_token": token},
                    )
                    replies_data = replies_resp.json()
                    for reply in replies_data.get("data", []):
                        rid = reply["id"]
                        if rid in processed:
                            continue
                        if reply.get("from", {}).get("id") == ig_id:
                            processed[rid] = time.time()
                            continue
                        try:
                            await client.post(
                                f"{_GRAPH_BASE}/{rid}/likes",
                                data={"access_token": token},
                            )
                            liked += 1
                        except Exception as e:
                            errors.append(f"like reply {rid}: {e}")
                        processed[rid] = time.time()
                except Exception as e:
                    errors.append(f"replies {cid}: {e}")

    _save_processed(processed)
    return {"liked": liked, "replied": replied, "errors": errors}
