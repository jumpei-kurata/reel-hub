"""スリープ起床ごとに1回だけ走る自動保守。

Render 無料枠を「寝かせて」運用する(常時起動しない=月間インスタンス時間を節約)。
サービスは GitHub Actions の起こし役(.github/workflows/reel-hub-wake.yml)が 3時間ごとに
/ping を叩いて起こす(ユーザーが開かなくても回る)。起床(=コールドスタート)するたびに
main.py の lifespan がこの関数をバックグラウンドで1回キックし:

  1) Instagram の新規コメントを処理(いいね＋絵文字返信)
     - 再いいね(toggleで外れる)は Upstash の永続dedupストアで防ぐ(instagram_comments.py)
  2) Facebook トークンの残り日数を確認し、閾値(既定25日・TOKEN_REFRESH_THRESHOLD_DAYS)を
     切っていれば自動更新(Render env 書換→再デプロイを伴う)

例外は全て握りつぶし、アプリ本体・ユーザーリクエストには一切影響させない。

3時間ごとの起床で常に最新を保つため 60日トークンなら永久に切れない
(現本番トークンは無期限型なので更新自体は発火しない)。
"""
import logging
import os
import time
from typing import Optional

import httpx

from app.config import (
    FACEBOOK_APP_ID,
    FACEBOOK_APP_SECRET,
    FACEBOOK_PAGE_ACCESS_TOKEN,
    INSTAGRAM_BUSINESS_ACCOUNT_ID,
)
from app.services.token_refresh import refresh_facebook_token

logger = logging.getLogger("reel_hub.auto_maintenance")

_FB_BASE = "https://graph.facebook.com/v19.0"
# 残り日数がこれ未満なら更新。60日トークンを十分手前で巻き直すための安全マージン。
# 環境変数 TOKEN_REFRESH_THRESHOLD_DAYS で上書き可(不正値は 25 にフォールバック)。
try:
    _REFRESH_THRESHOLD_DAYS = int(os.getenv("TOKEN_REFRESH_THRESHOLD_DAYS", "25"))
except ValueError:
    _REFRESH_THRESHOLD_DAYS = 25


async def token_status() -> dict:
    """トークンの健康診断。{"days": Optional[float], "reason": str} を返す。
    days が None のとき reason に原因が入る(診断用)。"""
    if not FACEBOOK_PAGE_ACCESS_TOKEN:
        return {"days": None, "reason": "FACEBOOK_PAGE_ACCESS_TOKEN 未設定"}
    if not (FACEBOOK_APP_ID and FACEBOOK_APP_SECRET):
        return {
            "days": None,
            "reason": "FACEBOOK_APP_ID / FACEBOOK_APP_SECRET 未設定(サーバー側) → 残日数取得も自動更新も不可",
        }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{_FB_BASE}/debug_token",
                params={
                    "input_token": FACEBOOK_PAGE_ACCESS_TOKEN,
                    "access_token": f"{FACEBOOK_APP_ID}|{FACEBOOK_APP_SECRET}",
                },
            )
            body = r.json() if r.content else {}
    except Exception as e:  # ネットワーク/JSON 失敗は致命ではない
        logger.warning("debug_token check failed: %s", e)
        return {"days": None, "reason": f"debug_token リクエスト失敗: {e}"}
    if isinstance(body, dict) and body.get("error"):
        return {"days": None, "reason": f"debug_token エラー: {body['error'].get('message')}"}
    data = body.get("data", {}) if isinstance(body, dict) else {}
    expires_at = data.get("expires_at")
    is_valid = data.get("is_valid")
    if expires_at == 0:
        if is_valid is False:
            return {"days": None, "reason": "トークン無効 (is_valid=False, expires_at=0)"}
        return {"days": None, "reason": "無期限トークン(更新不要・切れない)"}
    if not expires_at:
        return {"days": None, "reason": f"debug_token に expires_at 無し (is_valid={is_valid})"}
    days = round((expires_at - time.time()) / 86400.0, 1)
    return {"days": days, "reason": "ok" if is_valid else f"トークン無効 (is_valid={is_valid})"}


async def token_days_remaining() -> Optional[float]:
    """残り有効日数。判定不能 / 無期限 なら None。"""
    return (await token_status()).get("days")


async def maybe_refresh_token() -> None:
    days = await token_days_remaining()
    if days is None:
        logger.info("auto-maintenance: token expiry unknown - skip refresh")
        return
    logger.info("auto-maintenance: token has %.1f days remaining", days)
    if days < _REFRESH_THRESHOLD_DAYS:
        logger.info("auto-maintenance: below %d-day threshold - refreshing token", _REFRESH_THRESHOLD_DAYS)
        result = await refresh_facebook_token()
        logger.info("auto-maintenance: refresh result = %s", result)


async def _process_comments_safe() -> None:
    if not (FACEBOOK_PAGE_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ACCOUNT_ID):
        logger.info("auto-maintenance: IG not configured - skip comments")
        return
    from app.services.instagram_comments import process_comments

    result = await process_comments(reset=False)
    logger.info("auto-maintenance: comments = %s", result)


async def run_wake_maintenance() -> None:
    """起床ごとに1回。各ステップの例外は吸収し、アプリ本体には波及させない。

    順序: コメント処理(現トークンで確実に動く) → トークン更新チェック
    (更新が走ると再デプロイで本プロセスは落ちるが、コメントは先に済ませてある)。
    """
    try:
        await _process_comments_safe()
    except Exception as e:
        logger.warning("auto-maintenance: comment step failed: %s", e)
    try:
        await maybe_refresh_token()
    except Exception as e:
        logger.warning("auto-maintenance: refresh step failed: %s", e)
