# main.py — Nest Realtor Backend (SA) — stable + credits + DB init
import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional


from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from backend.ai.resolve_query import router as ai_router


load_dotenv()

# 1️⃣ Create app FIRST
app = FastAPI(
    title="Nest Realtor Backend",
    version="1.0.0"
)

# 2️⃣ INCLUDE ROUTERS IMMEDIATELY AFTER
app.include_router(ai_router)

# 3️⃣ Then define routes
@app.get("/health")
def health():
    return {"status": "ok"}


# --------------------------
# Logging
# --------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nest-realtor")

# --------------------------
# Config
# --------------------------
API_TOKEN = os.getenv("API_TOKEN")  # set on Render
SUPABASE_URL = os.getenv("SUPABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LIMIT = int(os.getenv("LEADS_LIMIT", "5"))   # leads per refresh
FREE_SEARCHES = int(os.getenv("FREE_SEARCHES", "5"))

# --------------------------
# Optional OpenAI (best-effort)
# --------------------------
try:
    if OPENAI_API_KEY:
        import openai
        openai.api_key = OPENAI_API_KEY
    else:
        openai = None
except Exception as e:
    openai = None
    logger.warning("OpenAI import failed: %s", e)

# --------------------------
# Import local modules (bots + database models)
# --------------------------
try:
    import bots
except Exception as e:
    bots = None
    logger.warning("bots.py import failed: %s", e)

# database.py should expose: engine, SessionLocal, Base, and model classes
try:
    from database import SessionLocal, Base, engine, BuyerLead, SellerLead, SocialLead, UniversalScrape, UserUsage
    HAS_DB = True
except Exception as e:
    # safe fallback: no DB (still allow scraping in memory)
    SessionLocal = None
    Base = None
    engine = None
    BuyerLead = SellerLead = SocialLead = UniversalScrape = UserUsage = None
    HAS_DB = False
    logger.warning("database.py import failed or incomplete: %s", e)

app = FastAPI(title="Nest Realtor Backend (SA)", version="1.0.0")

# ----------------------
# Create DB tables on startup (safe)
# ----------------------
@app.on_event("startup")
def init_on_startup():
    try:
        if HAS_DB and Base is not None and engine is not None:
            Base.metadata.create_all(bind=engine)
            logger.info("DB tables verified/created")
    except Exception as e:
        logger.exception("Failed to create DB tables on startup: %s", e)

# ----------------------
# Helpers
# ----------------------
def standard_response(success=True, data=None, error=None, status_code: int = 200):
    return JSONResponse(status_code=status_code, content={"success": success, "data": data or {}, "error": error})

def _get_token_from_headers(authorization: Optional[str], x_api_key: Optional[str], x_api_token: Optional[str]) -> Optional[str]:
    if x_api_key:
        return x_api_key
    if x_api_token:
        return x_api_token
    if authorization:
        # expects "Bearer <token>" or raw token
        if isinstance(authorization, str) and authorization.lower().startswith("bearer "):
            return authorization.split(" ", 1)[1].strip()
        return authorization.strip()
    return None

def _validate_token(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
    x_api_token: Optional[str] = Header(None, alias="x-api-token"),
) -> str:
    """
    Validates and returns a user identifier string.
    Skips auth for GET / and GET /health (Render health checks).
    """
    path = request.url.path
    if path in ("/", "/health"):
        return "anonymous"

    token = _get_token_from_headers(authorization, x_api_key, x_api_token)
    if not token:
        logger.debug("Missing API token on path %s", path)
        raise HTTPException(status_code=401, detail="Missing API token")

    # If API_TOKEN configured, accept exact match as 'service'
    if API_TOKEN:
        if token == API_TOKEN:
            return "service"

    # Attempt Supabase verify if configured (best-effort)
    if SUPABASE_URL:
        try:
            import requests as _requests
            r = _requests.get(f"{SUPABASE_URL}/auth/v1/user", headers={"Authorization": f"Bearer {token}"}, timeout=6)
            if r.status_code == 200:
                data = r.json()
                uid = data.get("id")
                if uid:
                    return uid
        except Exception:
            pass

    # If API_TOKEN is set and token didn't match, reject
    if API_TOKEN:
        logger.debug("Invalid API token provided")
        raise HTTPException(status_code=401, detail="Invalid API token")

    # fallback: use token as user id (dev mode)
    return token

# ----------------------
# Credit / usage helpers (uses UserUsage model when available)
# ----------------------
def get_or_create_usage(db, user_id: str):
    if not HAS_DB:
        return None
    usage = db.query(UserUsage).filter(UserUsage.user_id == user_id).first()
    if usage:
        return usage
    usage = UserUsage(user_id=user_id, used_searches=0, credits=0)
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage

def consume_credit_or_free(user_id: str) -> bool:
    """
    Atomically consume 1 credit or a free search for user_id.
    Returns True if allowed, False if no credits/free searches left.
    If no DB present, defaults to True (allow) for convenience.
    """
    if not HAS_DB or SessionLocal is None:
        # dev mode: allow
        return True
    db = SessionLocal()
    try:
        usage = db.query(UserUsage).filter(UserUsage.user_id == user_id).with_for_update().first()
        if not usage:
            usage = UserUsage(user_id=user_id, used_searches=0, credits=0)
            db.add(usage)
            db.commit()
            db.refresh(usage)
        if usage.credits and usage.credits > 0:
            usage.credits -= 1
            usage.last_updated = datetime.utcnow()
            db.commit()
            return True
        if usage.used_searches < FREE_SEARCHES:
            usage.used_searches += 1
            usage.last_updated = datetime.utcnow()
            db.commit()
            return True
        return False
    except Exception as e:
        logger.exception("consume_credit_or_free error: %s", e)
        # On DB error be permissive to avoid blocking tests — caller will still see DB warnings
        return True
    finally:
        db.close()

# ----------------------
# Background DB save helpers (no-op if DB missing)
# ----------------------
def _bg_save_buyer(user_id: str, results: list):
    if not HAS_DB or not results:
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
    except Exception:
        logger.exception("Failed to save buyer results in background")
    finally:
        db.close()

def _bg_save_seller(user_id: str, results: list):
    if not HAS_DB or not results:
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
    except Exception:
        logger.exception("Failed to save seller results in background")
    finally:
        db.close()

def _bg_save_social(user_id: str, platform: str, results: list):
    if not HAS_DB or not results:
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
    except Exception:
        logger.exception("Failed to save social results in background")
    finally:
        db.close()

def _bg_save_universal(user_id: str, payload: dict):
    if not HAS_DB or not payload:
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
    except Exception:
        logger.exception("Failed to save universal scrape in background")
    finally:
        db.close()

# ----------------------
# Async helper to run blocking bots in executor
# ----------------------
async def _run_sync(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

# ----------------------
# Root & health (public)
# ----------------------
@app.get("/")
def root():
    return standard_response(data={"message":"Nest Realtor Backend Running"})

@app.get("/health")
def health_check():
    return standard_response(data={"status":"ok","time": datetime.utcnow().isoformat()})

# ----------------------
# Buyers endpoint (consumes credit/free)
# ----------------------
@app.get("/leads/buyers")
async def get_buyer_leads(
    location: str,
    background: BackgroundTasks,
    user_id: str = Depends(_validate_token),
):
    if not bots or not hasattr(bots, "search_buyer_leads"):
        return standard_response(success=False, error="search_buyer_leads not implemented", data={})

    # credit check (skip for anonymous/service)
    if user_id not in ("anonymous", "service"):
        allowed = consume_credit_or_free(user_id)
        if not allowed:
            return standard_response(success=False, error="No free searches left — purchase credits", status_code=402)

    loc = (location or "").strip().replace(" ", "-").lower()
    try:
        resp = await _run_sync(bots.search_buyer_leads, loc, LIMIT)
    except Exception as e:
        logger.exception("search_buyer_leads error: %s", e)
        return standard_response(success=False, error=str(e))
    if not resp or resp.get("status") != "success":
        return standard_response(success=False, error=resp or "no results")
    results = (resp.get("results") or [])[:LIMIT]
    background.add_task(_bg_save_buyer, user_id, results)
    return standard_response(data={"count": len(results), "results": results})

# ----------------------
# Sellers endpoint (consumes credit/free)
# ----------------------
@app.get("/leads/sellers")
async def get_seller_leads(
    location: str,
    background: BackgroundTasks,
    user_id: str = Depends(_validate_token),
):
    if not bots or not hasattr(bots, "search_seller_leads"):
        return standard_response(success=False, error="search_seller_leads not implemented", data={})

    if user_id not in ("anonymous", "service"):
        allowed = consume_credit_or_free(user_id)
        if not allowed:
            return standard_response(success=False, error="No free searches left — purchase credits", status_code=402)

    loc = (location or "").strip().replace(" ", "-").lower()
    try:
        resp = await _run_sync(bots.search_seller_leads, loc, LIMIT)
    except Exception as e:
        logger.exception("search_seller_leads error: %s", e)
        return standard_response(success=False, error=str(e))
    if not resp or resp.get("status") != "success":
        return standard_response(success=False, error=resp or "no results")
    results = (resp.get("results") or [])[:LIMIT]
    background.add_task(_bg_save_seller, user_id, results)
    return standard_response(data={"count": len(results), "results": results})

# ----------------------
# Social endpoint (consumes credit/free)
# ----------------------
@app.get("/leads/social")
async def get_social_leads(
    platform: str = "instagram",
    query: str = "",
    background: BackgroundTasks = None,
    user_id: str = Depends(_validate_token),
):
    if not bots or not hasattr(bots, "social_media_leads"):
        return standard_response(success=False, error="social_media_leads not implemented", data={})

    if user_id not in ("anonymous", "service"):
        allowed = consume_credit_or_free(user_id)
        if not allowed:
            return standard_response(success=False, error="No free searches left — purchase credits", status_code=402)

    q = (query or "").strip()
    try:
        resp = await _run_sync(bots.social_media_leads, q, platform, LIMIT)
    except Exception as e:
        logger.exception("social_media_leads error: %s", e)
        return standard_response(success=False, error=str(e))
    if not resp or resp.get("status") != "success":
        return standard_response(success=False, error=resp or "no results")
    results = (resp.get("results") or [])[:LIMIT]
    background.add_task(_bg_save_social, user_id, platform, results)
    return standard_response(data={"count": len(results), "results": results})

# ----------------------
# Universal scraper (single url) — consumes credit/free
# ----------------------
@app.post("/leads/universal")
async def post_universal_scrape(
    body: dict,
    background: BackgroundTasks,
    user_id: str = Depends(_validate_token),
):
    url = (body or {}).get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Missing url")
    if not bots or not hasattr(bots, "universal_lead_scraper"):
        return standard_response(success=False, error="universal_lead_scraper not implemented", data={})

    if user_id not in ("anonymous", "service"):
        allowed = consume_credit_or_free(user_id)
        if not allowed:
            return standard_response(success=False, error="No free searches left — purchase credits", status_code=402)

    try:
        resp = await _run_sync(bots.universal_lead_scraper, url)
    except Exception as e:
        logger.exception("universal_lead_scraper error: %s", e)
        return standard_response(success=False, error=str(e))
    if not resp or resp.get("status") != "success":
        return standard_response(success=False, error=resp or "no results")
    # background save
    background.add_task(_bg_save_universal, user_id, resp)
    return standard_response(data={"result": resp})

# ----------------------
# Generate single lead endpoint (uses bots.generate_lead) — consumes credit/free
# ----------------------
@app.post("/generate-lead")
async def generate_lead_endpoint(
    body: dict,
    background: BackgroundTasks,
    user_id: str = Depends(_validate_token),
):
    if not bots or not hasattr(bots, "generate_lead"):
        return standard_response(success=False, error="generate_lead not implemented", data={})

    if user_id not in ("anonymous", "service"):
        allowed = consume_credit_or_free(user_id)
        if not allowed:
            return standard_response(success=False, error="No free searches left — purchase credits", status_code=402)

    try:
        if asyncio.iscoroutinefunction(bots.generate_lead):
            lead = await bots.generate_lead(user_id, body)
        else:
            lead = await _run_sync(bots.generate_lead, user_id, body)
    except Exception as e:
        logger.exception("generate_lead error: %s", e)
        return standard_response(success=False, error=str(e))
    if not lead:
        return standard_response(success=False, error="no lead generated")
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
async def store_lead_endpoint(
    body: dict,
    background: BackgroundTasks,
    user_id: str = Depends(_validate_token),
):
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
        logger.exception("store_lead error: %s", e)
        return standard_response(success=False, error=str(e))

# ----------------------
# Get saved leads (from DB)
# ----------------------
@app.get("/leads")
async def get_saved_leads(
    user_id: str = Depends(_validate_token),
):
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
    except Exception:
        logger.exception("get_saved_leads error")
        return standard_response(success=False, error="Failed to read leads")
    finally:
        db.close()

# ----------------------
# Local runner (only for local dev)
# ----------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)