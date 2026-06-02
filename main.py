import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from app.routes import admin, download, facebook, health
from app.routes.instagram import router as instagram_router
from app.config import DOWNLOAD_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    # スリープからの起床ごとに、自動保守(コメント処理＋トークン更新チェック)を
    # バックグラウンドで1回だけキック。起動はブロックしない。GC回避のため参照保持。
    from app.services.auto_maintenance import run_wake_maintenance

    app.state.maintenance_task = asyncio.create_task(run_wake_maintenance())
    yield


app = FastAPI(title="Reel Hub", lifespan=lifespan)

app.include_router(health.router)
app.include_router(download.router, prefix="/api")
app.include_router(facebook.router, prefix="/api")
app.include_router(instagram_router)
app.include_router(admin.router)


@app.get("/", include_in_schema=False)
async def index():
    # iOS Safari の HTML キャッシュ対策で毎回再検証させる
    return FileResponse(
        "app/static/index.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
