import json
import os
import random
import time
import unicodedata

import httpx

from app.config import FACEBOOK_PAGE_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID

_GRAPH_BASE = "https://graph.facebook.com/v19.0"

# 永続dedupストア(Upstash Redis REST)。Render無料枠は寝ると /tmp が消えるため、
# /tmp 方式だと起床のたびに既いいねを再POST→toggleで外れる。Upstashで「いいね済み」を永続化する。
_UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")
_UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
_PROCESSED_KEY = "reel-hub:processed_comments"
_REPLY_PATTERNS = [
    "🔥🔥",
    "🔥🔥🔥",
    "🔥❤️",
    "❤️🔥",
    "🔥😎",
    "😎🔥",
    "🔥👏",
    "👏👏",
    "🙌🔥",
    "🙌🙌",
    "💪🔥",
    "❤️‍🔥🔥",
    "🥹🔥",
]
_TTL_SECONDS = 30 * 24 * 60 * 60  # 30日


def _format_api_error(prefix: str, r: httpx.Response) -> str:
    try:
        body = r.json()
    except Exception:
        body = {}
    err = body.get("error", {}) if isinstance(body, dict) else {}
    return (
        f"{prefix}: HTTP {r.status_code} "
        f"code={err.get('code')} subcode={err.get('error_subcode')} "
        f"trace={err.get('fbtrace_id')} "
        f"msg={err.get('message') or r.text[:200]}"
    )


def _is_error_response(r: httpx.Response) -> bool:
    if r.status_code >= 400:
        return True
    try:
        body = r.json()
    except Exception:
        return False
    return isinstance(body, dict) and "error" in body


def dedup_store_available() -> bool:
    """永続dedupストア(Upstash)が設定されているか。未設定なら自動いいねは無効化する。"""
    return bool(_UPSTASH_URL and _UPSTASH_TOKEN)


async def _upstash(client: httpx.AsyncClient, *cmd: str):
    r = await client.post(
        _UPSTASH_URL,
        headers={"Authorization": f"Bearer {_UPSTASH_TOKEN}"},
        json=list(cmd),
    )
    r.raise_for_status()
    return r.json().get("result")


async def dedup_store_health() -> str:
    """/auth/status 用の疎通確認。'ok' / 'not_configured' / 'error: ...'。"""
    if not dedup_store_available():
        return "not_configured"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            pong = await _upstash(client, "PING")
        return "ok" if str(pong).upper() == "PONG" else f"unexpected: {pong}"
    except Exception as e:
        return f"error: {e}"


async def _load_processed(client: httpx.AsyncClient) -> dict:
    """Upstash から処理済みID(TTL付き)を読む。読めなければ例外を投げ、
    呼び出し側は再いいねによる toggle を避けるため処理を中止する。"""
    raw = await _upstash(client, "GET", _PROCESSED_KEY)
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        now = time.time()
        data = {k: now for k in data}
    cutoff = time.time() - _TTL_SECONDS
    return {k: v for k, v in data.items() if v > cutoff}


async def _save_processed(client: httpx.AsyncClient, ids: dict) -> None:
    await _upstash(client, "SET", _PROCESSED_KEY, json.dumps(ids))


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


async def _already_replied(client: httpx.AsyncClient, comment_id: str, ig_id: str, token: str) -> bool:
    """自分のIGアカウントが既にこのコメントに返信しているか確認（サーバー再起動後の重複返信防止）"""
    resp = await client.get(
        f"{_GRAPH_BASE}/{comment_id}/replies",
        params={"fields": "from", "access_token": token},
    )
    data = resp.json()
    return any(r.get("from", {}).get("id") == ig_id for r in data.get("data", []))


async def process_comments(reset: bool = False) -> dict:
    # 永続dedupストアが無いと再いいね→toggleで既存いいねを壊すため、いいね自体を行わない。
    if not dedup_store_available():
        return {"skipped": "dedup store (Upstash) 未設定のため自動いいねを停止中(既存いいねを誤って外さないため)"}

    token = FACEBOOK_PAGE_ACCESS_TOKEN
    ig_id = INSTAGRAM_BUSINESS_ACCOUNT_ID
    liked = 0
    replied = 0
    errors = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        # 処理済みID(永続)をロード。読めなければ「空」で進めず中止する(再いいね防止)。
        try:
            processed = {} if reset else await _load_processed(client)
        except Exception as e:
            return {"error": f"dedup store 読み取り失敗のため中止(再いいねによる toggle 防止): {e}"}

        media_resp = await client.get(
            f"{_GRAPH_BASE}/{ig_id}/media",
            params={"fields": "id", "limit": 10, "access_token": token},
        )
        media_data = media_resp.json()
        if "error" in media_data:
            return {"error": media_data["error"].get("message", str(media_data["error"]))}

        for media in media_data.get("data", []):
            media_id = media["id"]

            comments_resp = await client.get(
                f"{_GRAPH_BASE}/{media_id}/comments",
                params={"fields": "id,text,timestamp,from", "access_token": token},
            )
            comments_data = comments_resp.json()
            if "error" in comments_data:
                errors.append(f"media {media_id}: {comments_data['error'].get('message', comments_data['error'])}")
                continue

            for comment in comments_data.get("data", []):
                cid = comment["id"]

                if cid not in processed:
                    # 自分のコメントはスキップ（いいね・返信しない）
                    if comment.get("from", {}).get("id") == ig_id:
                        processed[cid] = time.time()
                    else:
                        text = comment.get("text", "")

                        # いいね（IGはコメント側に likes エッジが無い。POST /{ig_user_id}/likes に comment_id を渡す形）
                        try:
                            r = await client.post(
                                f"{_GRAPH_BASE}/{ig_id}/likes",
                                data={"comment_id": cid, "access_token": token},
                            )
                            if _is_error_response(r):
                                errors.append(_format_api_error(f"like {cid}", r))
                            else:
                                liked += 1
                        except Exception as e:
                            errors.append(f"like {cid}: {e}")

                        # 絵文字のみなら返信（APIで重複チェック・パターンランダム）
                        if is_emoji_only(text):
                            try:
                                if not await _already_replied(client, cid, ig_id, token):
                                    r = await client.post(
                                        f"{_GRAPH_BASE}/{cid}/replies",
                                        data={"message": random.choice(_REPLY_PATTERNS), "access_token": token},
                                    )
                                    if _is_error_response(r):
                                        errors.append(_format_api_error(f"reply {cid}", r))
                                    else:
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
                    if "error" in replies_data:
                        errors.append(f"replies {cid}: {replies_data['error'].get('message', replies_data['error'])}")
                        continue
                    for reply in replies_data.get("data", []):
                        rid = reply["id"]
                        if rid in processed:
                            continue
                        if reply.get("from", {}).get("id") == ig_id:
                            processed[rid] = time.time()
                            continue
                        try:
                            r = await client.post(
                                f"{_GRAPH_BASE}/{ig_id}/likes",
                                data={"comment_id": rid, "access_token": token},
                            )
                            if _is_error_response(r):
                                errors.append(_format_api_error(f"like reply {rid}", r))
                            else:
                                liked += 1
                        except Exception as e:
                            errors.append(f"like reply {rid}: {e}")
                        processed[rid] = time.time()
                except Exception as e:
                    errors.append(f"replies {cid}: {e}")

        await _save_processed(client, processed)
    return {"liked": liked, "replied": replied, "errors": errors}
