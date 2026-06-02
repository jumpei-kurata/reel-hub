import os
import secrets

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.config import REFRESH_SECRET

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"status": "ok"}


@router.get("/auth/status")
async def auth_status(secret: str = ""):
    # 公開は基本ブールのみ。詳細診断(残日数・null理由・必要envの設定状況)は
    # 認証情報の設定状況を無認証で列挙させないため ?secret= 必須。
    result = {
        "facebook_configured": bool(os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")) and bool(os.getenv("FACEBOOK_PAGE_ID")),
        "instagram_configured": bool(os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")),
    }
    if REFRESH_SECRET and secret and secrets.compare_digest(secret, REFRESH_SECRET):
        from app.services.auto_maintenance import token_status

        try:
            ts = await token_status()
        except Exception as e:
            ts = {"days": None, "reason": f"status error: {e}"}
        result["token_days_remaining"] = ts.get("days")
        result["token_check"] = ts.get("reason")
        result["config_present"] = {
            "FACEBOOK_APP_ID": bool(os.getenv("FACEBOOK_APP_ID")),
            "FACEBOOK_APP_SECRET": bool(os.getenv("FACEBOOK_APP_SECRET")),
            "RENDER_API_KEY": bool(os.getenv("RENDER_API_KEY")),
            "RENDER_SERVICE_ID": bool(os.getenv("RENDER_SERVICE_ID")),
            "REFRESH_SECRET": bool(os.getenv("REFRESH_SECRET")),
            "UPSTASH_REDIS_REST_URL": bool(os.getenv("UPSTASH_REDIS_REST_URL")),
            "UPSTASH_REDIS_REST_TOKEN": bool(os.getenv("UPSTASH_REDIS_REST_TOKEN")),
        }
        from app.services.instagram_comments import dedup_store_health

        try:
            result["dedup_store"] = await dedup_store_health()
        except Exception as e:
            result["dedup_store"] = f"error: {e}"
    return result


_TERMS_HTML = """<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><title>利用規約 - Reel Hub</title>
<style>body{font-family:sans-serif;max-width:600px;margin:40px auto;padding:0 20px;line-height:1.6}</style></head>
<body><h1>利用規約</h1><p>本ツール（Reel Hub）は、運営者個人が自身のSNSコンテンツを管理するためのプライベートツールです。</p>
<h2>利用条件</h2><ul><li>本ツールは運営者のみが使用します。</li><li>取得したコンテンツは自身のアカウントへの再投稿にのみ使用します。</li>
<li>第三者のコンテンツの無断使用は行いません。</li></ul>
<h2>免責事項</h2><p>本ツールの利用により生じたいかなる損害についても、運営者は責任を負いません。</p>
<p>最終更新日: 2024年1月</p></body></html>"""

_PRIVACY_HTML = """<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><title>プライバシーポリシー - Reel Hub</title>
<style>body{font-family:sans-serif;max-width:600px;margin:40px auto;padding:0 20px;line-height:1.6}</style></head>
<body><h1>プライバシーポリシー</h1><p>本ツール（Reel Hub）のプライバシーポリシーについて説明します。</p>
<h2>収集する情報</h2><p>本ツールは運営者個人のみが使用するプライベートツールであり、第三者の個人情報を収集・保存しません。</p>
<h2>Facebookとの連携</h2><p>Facebook APIを通じて取得するデータは、ページへのコンテンツ投稿のみに使用します。</p>
<h2>データの保管</h2><p>一時的にダウンロードした動画ファイルはサーバー再起動時に削除されます。</p>
<p>最終更新日: 2024年1月</p></body></html>"""



@router.get("/terms", response_class=HTMLResponse)
async def terms():
    return _TERMS_HTML


@router.get("/privacy", response_class=HTMLResponse)
async def privacy():
    return _PRIVACY_HTML
