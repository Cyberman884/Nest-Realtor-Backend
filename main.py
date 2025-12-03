# main.py — Core Nest Realtor Backend (clean, minimal, core endpoints)
import os
import json
import asyncio
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import requests
import openai

# local modules (bots.py should exist)
try:
    import bots
except Exception:
    bots = None

# Optional DB helpers if present in your repo (best-effort import)
try:
    from database import SessionLocal, BuyerLead, SellerLead, SocialLead
    HAS_DB = True
except Exception:
    SessionLocal = None
    BuyerLead = SellerLead = SocialLead = None
    HAS_DB = False

load_dotenv()

# Config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
API_TOKEN = os.getenv("API_TOKEN")  # set this on Render for simple auth
SUPABASE_URL = os.getenv("SUPABASE_URL")

if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

app = FastAPI(title="Nest Realtor — Core Backend", docs_url="/docs", redoc_url="/redoc")

# CORS (open; tighten allowed origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------
# Utilities & helpers
# ----------------------
def _resp(success: bool, data=None, error: Optional[str] = None, status_code: int = 200):
    return JSONResponse(status_code=status_code, content={"success": success, "data": data or {}, "error": error})

def _validate_token_header(authorization: Optional[str]) -> str:
    """
    Validate Authorization header and return a user identifier.
    - If API_TOKEN set and matches, return 'service'
    - If SUPABASE_URL set, attempt a quick user lookup
    - Otherwise return token string as fallback (dev)
    Raises HTTPException(401) if header missing/invalid.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    # API token bypass
    if API_TOKEN and token == API_TOKEN:
        return "service"
    # Optional Supabase verify
    if SUPABASE_URL:
        try:
            r = requests.get(f"{SUPABASE_URL}/auth/v1/user", headers={"Authorization": f"Bearer {token}"}, timeout=6)
            if r.status_code == 200:
                data = r.json()
                uid = data.get("id")
                if uid:
                    return uid
        except Exception:
            # fall through to return token as fallback
            pass
    return token

async def _run_sync(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

# Background DB saves (safe no-op if DB not present)
def _bg_save_buyer(user_id: str, results: list):
    if not HAS_DB:
        return
    db = SessionLocal()
    try:
        for r in results:
            entry = BuyerLead(user_id=user_id, title=r.get("title",""), price=r.get("price",""), link=r.get("link"), raw=json.dumps(r))
            db.add(entry)
        db.commit()
    finally:
        db.close()

def _bg_save_social(user_id: str, platform: str, results: list):
    if not HAS_DB:
        return
    db = SessionLocal()
    try:
        for r in results:
            entry = SocialLead(user_id=user_id, platform=platform, title=r.get("title",""), link=r.get("link"), raw=json.dumps(r))
            db.add(entry)
        db.commit()
    finally:
        db.close()

# ----------------------
# Root & health
# ----------------------
@app.get("/")
def root():
    return _resp(True, {"message": "Nest Realtor Backend Running"})

@app.get("/health")
def health():
    return _resp(True, {"status": "ok", "time": datetime.utcnow().isoformat()})

# ----------------------
# AI filter (simple local filter; optional OpenAI ranking)
# ----------------------
@app.post("/ai-filter")
async def ai_filter_endpoint(request: Request, authorization: Optional[str] = Header(None)):
    _ = _validate_token_header(authorization)
    body = await request.json()
    leads = body.get("leads", [])
    # Basic de-dupe + normalize
    seen = set()
    cleaned = []
    for r in leads:
        link = (r.get("link") or r.get("url") or "").strip()
        if not link or link in seen:
            continue
        seen.add(link)
        cleaned.append({
            "title": r.get("title") or r.get("name") or "",
            "price": r.get("price") or r.get("budget") or "",
            "link": link,
            "platform": r.get("platform") or r.get("source") or "unknown",
            "raw": r
        })
    # Optional OpenAI enrichment/ranking (best-effort)
    if OPENAI_API_KEY and cleaned:
        try:
            prompt = "Rank these leads (0-100) by relevance and return JSON array with an added 'score' field."
            resp = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":prompt},{"role":"user","content": json.dumps(cleaned[:20])}],
                max_tokens=512
            )
            text = resp.choices[0].message["content"]
            parsed = json.loads(text)
            if isinstance(parsed, list):
                cleaned = parsed
        except Exception:
            pass
    return _resp(True, {"count": len(cleaned), "results": cleaned})

# ----------------------
# Scrape social (calls bots.social_media_leads)
# ----------------------
@app.post("/scrape/social")
async def scrape_social(request: Request, background: BackgroundTasks, authorization: Optional[str] = Header(None)):
    user_id = _validate_token_header(authorization)
    if bots is None or not hasattr(bots, "social_media_leads"):
        return _resp(False, {}, "social_media_leads not implemented in bots.py", status_code=500)

    body = await request.json()
    platform = (body.get("platform") or "instagram").lower()
    query = body.get("query", "").strip()
    limit = int(body.get("limit", 10))

    # run sync scraper in executor
    try:
        resp = await _run_sync(bots.social_media_leads, query, platform, limit) if asyncio.get_event_loop().is_running() else bots.social_media_leads(query, platform, limit)
    except Exception as e:
        return _resp(False, {}, f"Scraper error: {e}", status_code=500)

    if not resp or resp.get("status") != "success":
        return _resp(False, {}, "Scraping failed or no results", status_code=500)

    results = resp.get("results", [])[:limit]
    # background save if DB available
    background.add_task(_bg_save_social, user_id, platform, results)
    return _resp(True, {"count": len(results), "results": results})

# ----------------------
# Generate lead (calls bots.generate_lead or falls back to search_buyer_leads)
# ----------------------
@app.post("/generate-lead")
async def generate_lead(request: Request, background: BackgroundTasks, authorization: Optional[str] = Header(None)):
    user_id = _validate_token_header(authorization)
    body = await request.json()

    # prefer an async generate_lead in bots; otherwise run sync functions in executor
    try:
        if bots and hasattr(bots, "generate_lead"):
            # may be async
            gen_fn = bots.generate_lead
            if asyncio.iscoroutinefunction(gen_fn):
                lead = await gen_fn(user_id, body)
            else:
                lead = await _run_sync(gen_fn, user_id, body)
        else:
            # fallback to property search
            if bots and hasattr(bots, "search_buyer_leads"):
                resp = await _run_sync(bots.search_buyer_leads, body.get("location", ""), int(body.get("limit", 1)))
                lead = resp.get("results", [])[0] if resp and resp.get("results") else {}
            else:
                lead = {}
    except Exception as e:
        return _resp(False, {}, f"Lead generation failed: {e}", status_code=500)

    # background save buyer lead if DB present
    if lead:
        background.add_task(_bg_save_buyer, user_id, [lead])
    return _resp(True, {"lead": lead})

# ----------------------
# Store lead (saves to DB if available or returns stored data)
# ----------------------
@app.post("/store-lead")
async def store_lead(request: Request, authorization: Optional[str] = Header(None)):
    user_id = _validate_token_header(authorization)
    body = await request.json()
    lead_type = body.get("type", "buyer")

    try:
        if lead_type == "buyer":
            if HAS_DB:
                await _run_sync(_bg_save_buyer, user_id, [body])
                return _resp(True, {"stored": 1})
            else:
                return _resp(True, {"stored": 1, "lead": body})
        elif lead_type == "social":
            if HAS_DB:
                await _run_sync(_bg_save_social, user_id, body.get("platform", "unknown"), [body])
                return _resp(True, {"stored": 1})
            else:
                return _resp(True, {"stored": 1, "lead": body})
        else:
            # seller or other
            return _resp(True, {"stored": 0, "note": "Unsupported type in minimal backend"})
    except Exception as e:
        return _resp(False, {}, f"Store failed: {e}", status_code=500)

# ----------------------
# Get leads (reads from DB if available; else returns empty)
# ----------------------
@app.get("/leads")
async def get_leads(authorization: Optional[str] = Header(None)):
    user_id = _validate_token_header(authorization)
    if not HAS_DB:
        return _resp(True, {"buyer_leads": [], "seller_leads": [], "social_leads": []})
    db = SessionLocal()
    try:
        buyer = db.query(BuyerLead).filter(BuyerLead.user_id == user_id).all()
        seller = db.query(SellerLead).filter(SellerLead.user_id == user_id).all()
        social = db.query(SocialLead).filter(SocialLead.user_id == user_id).all()
        return _resp(True, {
            "buyer_leads": [json.loads(l.raw) for l in buyer],
            "seller_leads": [json.loads(l.raw) for l in seller],
            "social_leads": [json.loads(l.raw) for l in social],
        })
    finally:
        db.close()

# ----------------------
# Webhook (generic)
# ----------------------
@app.post("/webhook")
async def webhook_handler(request: Request, background: BackgroundTasks, authorization: Optional[str] = Header(None)):
    # Accept webhooks without auth (some providers can't add headers)
    try:
        body = await request.json()
    except Exception:
        body = {}
    user_id = body.get("user_id", None)
    if not user_id:
        # try auth header for user
        try:
            user_id = _validate_token_header(authorization)
        except Exception:
            user_id = "anonymous"
    # background save for tracking
    if HAS_DB:
        background.add_task(_bg_save_social, user_id or "anonymous", "webhook", [body])
    return _resp(True, {"received": body})

# ----------------------
# Local run helper
# ----------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)
