# main.py — Nest Realtor API (FastAPI) — SA-only scrapers wired, 5 leads per refresh
import os
import json
import asyncio
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

# local scrapers / bots
try:
    import bots
except Exception:
    bots = None

# optional DB models (safe import)
try:
    from database import SessionLocal, BuyerLead, SellerLead, SocialLead, UniversalScrape, UserUsage
    HAS_DB = True
except Exception:
    SessionLocal = None
    BuyerLead = SellerLead = SocialLead = UniversalScrape = UserUsage = None
    HAS_DB = False

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")  # must be set on Render
SUPABASE_URL = os.getenv("SUPABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if OPENAI_API_KEY:
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
    except Exception:
        openai = None

app = FastAPI(title="Nest Realtor Backend (SA)", version="1.0.0")

# Config
LIMIT = 5  # leads per refresh

# ----------------------
# Helper responses & utils
# ----------------------
def standard_response(success=True, data=None, error=None):
    return JSONResponse(content={"success": success, "data": data or {}, "error": error})

def _get_token_from_headers(authorization: Optional[str], x_api_key: Optional[str], x_api_token: Optional[str]) -> Optional[str]:
    if x_api_key:
        return x_api_key
    if x_api_token:
        return x_api_token
    if authorization:
        # support "Bearer <token>"
        if authorization.lower().startswith("bearer "):
            return authorization.split(" ", 1)[1].strip()
        return authorization.strip()
    return None

def _validate_token(authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None, alias="x-api-key"), x_api_token: Optional[str] = Header(None, alias="x-api-token")) -> str:
    token = _get_token_from_headers(authorization, x_api_key, x_api_token)
    if not token:
        raise HTTPException(status_code=401, detail="Missing API token")
    if API_TOKEN and token != API_TOKEN:
        # if SUPABASE_URL is configured we could verify token there, but default compare to API_TOKEN
        # attempt Supabase verify as fallback (best-effort)
        if SUPABASE_URL:
            try:
                import requests
                r = requests.get(f"{SUPABASE_URL}/auth/v1/user", headers={"Authorization": f"Bearer {token}"}, timeout=6)
                if r.status_code == 200:
                    data = r.json()
                    uid = data.get("id")
                    if uid:
                        return uid
            except Exception:
                pass
        raise HTTPException(status_code=401, detail="Invalid API token")
    # token valid; return identifier string for DB usage
    return token if not API_TOKEN else ("service" if token == API_TOKEN else token)

# ----------------------
# Background DB saves (no-op when DB missing)
# ----------------------
def _bg_save_buyer(user_id: str, results: list):
    if not HAS_DB:
        return
    db = SessionLocal()
    try:
        for r in results:
            entry = BuyerLead(
                user_id=user_id,
                title=r.get("title",""),
                price=str(r.get("price") or r.get("raw_price","")),
                link=r.get("link"),
                raw=json.dumps(r)
            )
            db.add(entry)
        db.commit()
    finally:
        db.close()

def _bg_save_seller(user_id: str, results: list):
    if not HAS_DB:
        return
    db = SessionLocal()
    try:
        for r in results:
            entry = SellerLead(
                user_id=user_id,
                title=r.get("title",""),
                link=r.get("link"),
                raw=json.dumps(r)
            )
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
            entry = SocialLead(
                user_id=user_id,
                platform=platform,
                title=r.get("title",""),
                link=r.get("link"),
                raw=json.dumps(r)
            )
            db.add(entry)
        db.commit()
    finally:
        db.close()

def _bg_save_universal(user_id: str, payload: dict):
    if not HAS_DB:
        return
    db = SessionLocal()
    try:
        entry = UniversalScrape(
            user_id=user_id,
            source_url=payload.get("source_url") or payload.get("url"),
            page_title=payload.get("page_title") or payload.get("title"),
            preview_text=payload.get("preview_text") or payload.get("text") or "",
            raw=json.dumps(payload)
        )
        db.add(entry)
        db.commit()
    finally:
        db.close()

# ----------------------
# Async helper to run blocking bots in executor
# ----------------------
async def _run_sync(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

# ----------------------
# Root & health
# ----------------------
@app.get("/")
def root():
    return standard_response(data={"message":"Nest Realtor Backend Running"})

@app.get("/health")
def health_check(user_id: str = Depends(_validate_token)):
    return standard_response(data={"status":"ok","time": datetime.utcnow().isoformat()})

# ----------------------
# Buyers endpoint
# ----------------------
@app.get("/leads/buyers")
async def get_buyer_leads(location: str, background: BackgroundTasks, user_id: str = Depends(_validate_token)):
    """
    Example: /leads/buyers?location=pretoria
    Returns up to LIMIT buyer leads from Property24 (SA)
    """
    if not bots or not hasattr(bots, "search_buyer_leads"):
        return standard_response(success=False, error="search_buyer_leads not implemented", data={})
    # normalize location for bots (replace spaces)
    loc = (location or "").strip().replace(" ", "-").lower()
    try:
        resp = await _run_sync(bots.search_buyer_leads, loc, LIMIT)
    except Exception as e:
        return standard_response(success=False, error=str(e))
    if not resp or resp.get("status") != "success":
        return standard_response(success=False, error=resp or "no results")
    results = (resp.get("results") or [])[:LIMIT]
    # background save
    background.add_task(_bg_save_buyer, user_id, results)
    return standard_response(data={"count": len(results), "results": results})

# ----------------------
# Sellers endpoint
# ----------------------
@app.get("/leads/sellers")
async def get_seller_leads(location: str, background: BackgroundTasks, user_id: str = Depends(_validate_token)):
    """
    Example: /leads/sellers?location=capetown
    """
    if not bots or not hasattr(bots, "search_seller_leads"):
        return standard_response(success=False, error="search_seller_leads not implemented", data={})
    loc = (location or "").strip().replace(" ", "-").lower()
    try:
        resp = await _run_sync(bots.search_seller_leads, loc, LIMIT)
    except Exception as e:
        return standard_response(success=False, error=str(e))
    if not resp or resp.get("status") != "success":
        return standard_response(success=False, error=resp or "no results")
    results = (resp.get("results") or [])[:LIMIT]
    background.add_task(_bg_save_seller, user_id, results)
    return standard_response(data={"count": len(results), "results": results})

# ----------------------
# Social endpoint
# ----------------------
@app.get("/leads/social")
async def get_social_leads(platform: str = "instagram", query: str = "", background: BackgroundTasks = None, user_id: str = Depends(_validate_token)):
    """
    Example: /leads/social?platform=instagram&query=pretoria
    """
    if not bots or not hasattr(bots, "social_media_leads"):
        return standard_response(success=False, error="social_media_leads not implemented", data={})
    q = (query or "").strip()
    try:
        resp = await _run_sync(bots.social_media_leads, q, platform, LIMIT)
    except Exception as e:
        return standard_response(success=False, error=str(e))
    if not resp or resp.get("status") != "success":
        return standard_response(success=False, error=resp or "no results")
    results = (resp.get("results") or [])[:LIMIT]
    background.add_task(_bg_save_social, user_id, platform, results)
    return standard_response(data={"count": len(results), "results": results})

# ----------------------
# Universal scraper (single url)
# ----------------------
@app.post("/leads/universal")
async def post_universal_scrape(body: dict, background: BackgroundTasks, user_id: str = Depends(_validate_token)):
    url = (body or {}).get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Missing url")
    if not bots or not hasattr(bots, "universal_lead_scraper"):
        return standard_response(success=False, error="universal_lead_scraper not implemented", data={})
    try:
        resp = await _run_sync(bots.universal_lead_scraper, url)
    except Exception as e:
        return standard_response(success=False, error=str(e))
    if not resp or resp.get("status") != "success":
        return standard_response(success=False, error=resp or "no results")
    # background save
    background.add_task(_bg_save_universal, user_id, resp)
    return standard_response(data={"result": resp})

# ----------------------
# Generate single lead endpoint (uses bots.generate_lead)
# ----------------------
@app.post("/generate-lead")
async def generate_lead_endpoint(body: dict, background: BackgroundTasks, user_id: str = Depends(_validate_token)):
    if not bots or not hasattr(bots, "generate_lead"):
        return standard_response(success=False, error="generate_lead not implemented", data={})
    try:
        # bots.generate_lead may be async
        if asyncio.iscoroutinefunction(bots.generate_lead):
            lead = await bots.generate_lead(user_id, body)
        else:
            lead = await _run_sync(bots.generate_lead, user_id, body)
    except Exception as e:
        return standard_response(success=False, error=str(e))
    if not lead:
        return standard_response(success=False, error="no lead generated")
    # Save generated lead (best-effort into buyer or seller)
    t = body.get("type","buyer")
    if t == "seller":
        background.add_task(_bg_save_seller, user_id, [lead])
    else:
        background.add_task(_bg_save_buyer, user_id, [lead])
    return standard_response(data={"lead": lead})

# ----------------------
# Store lead (store arbitrary lead payload)
# ----------------------
@app.post("/store-lead")
async def store_lead_endpoint(body: dict, background: BackgroundTasks, user_id: str = Depends(_validate_token)):
    """
    Accepts an object with fields like name, phone, email, type, source, location, price
    Stores in DB corresponding table if available, otherwise returns success with payload.
    """
    payload = body or {}
    t = payload.get("type","buyer")
    try:
        if HAS_DB:
            if t == "seller":
                await _run_sync(_bg_save_seller, user_id, [payload])
            elif t == "social":
                platform = payload.get("platform","social")
                await _run_sync(_bg_save_social, user_id, platform, [payload])
            else:
                await _run_sync(_bg_save_buyer, user_id, [payload])
            return standard_response(data={"stored": True})
        else:
            return standard_response(data={"stored": True, "lead": payload})
    except Exception as e:
        return standard_response(success=False, error=str(e))

# ----------------------
# Get saved leads (from DB)
# ----------------------
@app.get("/leads")
async def get_saved_leads(user_id: str = Depends(_validate_token)):
    if not HAS_DB:
        return standard_response(data={"buyer_leads": [], "seller_leads": [], "social_leads": []})
    db = SessionLocal()
    try:
        buyer = db.query(BuyerLead).filter(BuyerLead.user_id == user_id).all()
        seller = db.query(SellerLead).filter(SellerLead.user_id == user_id).all()
        social = db.query(SocialLead).filter(SocialLead.user_id == user_id).all()
        return standard_response(data={
            "buyer_leads": [json.loads(l.raw) for l in buyer],
            "seller_leads": [json.loads(l.raw) for l in seller],
            "social_leads": [json.loads(l.raw) for l in social]
        })
    finally:
        db.close()

# ----------------------
# Local runner
# ----------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)
