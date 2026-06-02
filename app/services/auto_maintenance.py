"""スリープ起床ごとに1回だけ走る自動保守。

Render 無料枠を「寝かせて」運用するため、外部スケジューラ(cron-job.org / GitHub Actions)を
一切使わず、アプリがコールドスタート(=スリープからの起床 = ユーザーアクセス)する度に:

  1) Instagram の新規コメントを処理(いいね＋絵文字返信)
  2) Facebook 長期トークンの残り日数を確認し、閾値を切っていれば自動更新(再デプロイを伴う)

を main.py の lifespan からバックグラウンドで1回キックする。
例外は全て握りつぶし、アプリ本体・ユーザーリクエストには一切影響させない。

トークンは毎回更新するのではなく「残り <25日」のときだけ更新する点が肝。
ユーザーが概ね毎日開く限り 60日トークンは永久に切れず、再デプロイは ~35日に1回で済む。
"""
import logging
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
_REFRESH_THRESHOLD_DAYS = 25


async def token_days_remaining() -> Optional[float]:
    """現在の FB トークンの残り有効日数を返す。判定不能 / 無期限 なら None。"""
    if not (FACEBOOK_APP_ID and FACEBOOK_APP_SECRET and FACEBOOK_PAGE_ACCESS_TOKEN):
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{_FB_BASE}/debug_token",
                params={
                    "input_token": FACEBOOK_PAGE_ACCESS_TOKEN,
                    "access_token": f"{FACEBOOK_APP_ID}|{FACEBOOK_APP_SECRET}",
                },
            )
            data = (r.json() or {}).get("data", {})
    except Exception as e:  # ネットワーク/JSON 失敗は致命ではない
        logger.warning("debug_token check failed: %s", e)
        return None
    expires_at = data.get("expires_at")
    if not expires_at:  # 0 = 無期限、または欠落 → 更新不要 / 判定不能
        return None
    return (expires_at - time.time()) / 86400.0


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
