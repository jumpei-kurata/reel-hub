import httpx

from app.config import (
    FACEBOOK_APP_ID,
    FACEBOOK_APP_SECRET,
    FACEBOOK_PAGE_ACCESS_TOKEN,
    RENDER_API_KEY,
    RENDER_SERVICE_ID,
)

_FB_BASE = "https://graph.facebook.com/v19.0"
_RENDER_BASE = "https://api.render.com/v1"
_ENV_VAR_KEY = "FACEBOOK_PAGE_ACCESS_TOKEN"


async def refresh_facebook_token() -> dict:
    missing = [
        name
        for name, val in [
            ("FACEBOOK_APP_ID", FACEBOOK_APP_ID),
            ("FACEBOOK_APP_SECRET", FACEBOOK_APP_SECRET),
            ("FACEBOOK_PAGE_ACCESS_TOKEN", FACEBOOK_PAGE_ACCESS_TOKEN),
            ("RENDER_API_KEY", RENDER_API_KEY),
            ("RENDER_SERVICE_ID", RENDER_SERVICE_ID),
        ]
        if not val
    ]
    if missing:
        return {"error": f"missing env vars: {', '.join(missing)}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{_FB_BASE}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": FACEBOOK_APP_ID,
                "client_secret": FACEBOOK_APP_SECRET,
                "fb_exchange_token": FACEBOOK_PAGE_ACCESS_TOKEN,
            },
        )
        try:
            data = r.json()
        except Exception:
            return {"error": f"fb_exchange_token: HTTP {r.status_code} body={r.text[:200]}"}
        if r.status_code >= 400 or "error" in data:
            return {"error": f"fb_exchange_token: HTTP {r.status_code} {data}"}
        new_token = data.get("access_token")
        expires_in = data.get("expires_in")
        if not new_token:
            return {"error": f"fb_exchange_token returned no access_token: {data}"}

        r2 = await client.put(
            f"{_RENDER_BASE}/services/{RENDER_SERVICE_ID}/env-vars/{_ENV_VAR_KEY}",
            headers={
                "Authorization": f"Bearer {RENDER_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={"value": new_token},
        )
        if r2.status_code >= 400:
            return {"error": f"render api: HTTP {r2.status_code} body={r2.text[:200]}"}

    return {"refreshed": True, "expires_in_seconds": expires_in}
