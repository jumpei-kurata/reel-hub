from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"status": "ok"}


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
<h2>TikTokとの連携</h2><p>TikTok APIを通じて取得するデータ（アクセストークン等）は、コンテンツ投稿のみに使用し、第三者と共有しません。</p>
<h2>Facebookとの連携</h2><p>Facebook APIを通じて取得するデータは、ページへのコンテンツ投稿のみに使用します。</p>
<h2>データの保管</h2><p>一時的にダウンロードした動画ファイルはサーバー再起動時に削除されます。</p>
<p>最終更新日: 2024年1月</p></body></html>"""


@router.get("/tiktokUoIBAU2M3OKbXL0V3Hhx95CPTkjwzQpA.txt", response_class=PlainTextResponse)
async def tiktok_verify():
    return "tiktok-developers-site-verification=UolBAU2M3OKbXL0V3Hhx95CPTkjwzQpA"


@router.get("/terms", response_class=HTMLResponse)
async def terms():
    return _TERMS_HTML


@router.get("/privacy", response_class=HTMLResponse)
async def privacy():
    return _PRIVACY_HTML
