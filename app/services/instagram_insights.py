import asyncio

import httpx

from app.config import FACEBOOK_PAGE_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID

_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_METRICS = "reach,saved,likes,comments,shares,views"


async def _fetch_one(client: httpx.AsyncClient, media: dict, token: str) -> dict:
    media_id = media["id"]
    ins_resp = await client.get(
        f"{_GRAPH_BASE}/{media_id}/insights",
        params={"metric": _METRICS, "access_token": token},
    )
    try:
        ins_data = ins_resp.json()
    except Exception:
        ins_data = {"error": {"message": f"HTTP {ins_resp.status_code} body={ins_resp.text[:200]}"}}

    insights: dict = {}
    if "error" in ins_data:
        err = ins_data["error"]
        insights["_error"] = err.get("message", str(err)) if isinstance(err, dict) else str(err)
    else:
        for item in ins_data.get("data", []):
            name = item.get("name")
            values = item.get("values") or [{}]
            insights[name] = values[0].get("value", 0)

    return {
        "id": media_id,
        "type": media.get("media_product_type") or media.get("media_type"),
        "timestamp": media.get("timestamp"),
        "permalink": media.get("permalink"),
        "caption": (media.get("caption") or "").splitlines()[0][:80],
        "insights": insights,
    }


async def get_recent_insights(limit: int = 10) -> dict:
    if not FACEBOOK_PAGE_ACCESS_TOKEN or not INSTAGRAM_BUSINESS_ACCOUNT_ID:
        return {"error": "missing FACEBOOK_PAGE_ACCESS_TOKEN or INSTAGRAM_BUSINESS_ACCOUNT_ID"}

    token = FACEBOOK_PAGE_ACCESS_TOKEN
    ig_id = INSTAGRAM_BUSINESS_ACCOUNT_ID

    async with httpx.AsyncClient(timeout=30.0) as client:
        media_resp = await client.get(
            f"{_GRAPH_BASE}/{ig_id}/media",
            params={
                "fields": "id,caption,media_type,media_product_type,timestamp,permalink",
                "limit": limit,
                "access_token": token,
            },
        )
        media_data = media_resp.json()
        if "error" in media_data:
            err = media_data["error"]
            return {"error": err.get("message", str(err)) if isinstance(err, dict) else str(err)}

        media_list = media_data.get("data", [])
        results = await asyncio.gather(*[_fetch_one(client, m, token) for m in media_list])

    results.sort(key=lambda x: x["insights"].get("views", 0), reverse=True)
    return {"count": len(results), "media": results}
