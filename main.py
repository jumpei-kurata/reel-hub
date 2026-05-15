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
