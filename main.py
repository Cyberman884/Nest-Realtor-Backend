# main.py — patched for Friday full wire-up
import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# local modules (ensure these exist / have correct names)
import bots   # your scrapers: property + placeholder social functions
from database import (
    SessionLocal, Base, engine,
    BuyerLead, SellerLead, SocialLead, UniversalScrape, PaymentRecord, UserUsage
)
from config import SUPABASE_URL, SUPABASE_KEY

load_dotenv()

app = FastAPI(title="Nest Realtor — Combined Backend (Property + SLS)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ensure tables exist
Base.metadata.create_all(bind=engine)

FREE_SEARCHES = 5

# ---------- helpers ----------
def _validate_supabase_token(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = header.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        r = requests.get(f"{SUPABASE_URL}/auth/v1/user", headers={"Authorization": f"Bearer {token}"}, timeout=8)
        if r.status_code == 200:
            return r.json().get("id")
    except Exception:
        pass
    raise HTTPException(status_code=401, detail="Invalid Supabase token")

# credit/usage functions (assumes UserUsage model exists)
from sqlalchemy.orm import Session
def get_or_create_usage(db: Session, user_id: str):
    usage = db.query(UserUsage).filter(UserUsage.user_id == user_id).first()
    if usage:
        return usage
    usage = UserUsage(user_id=user_id, used_searches=0, credits=0)
    db.add(usage); db.commit(); db.refresh(usage)
    return usage

def consume_credit_or_free(db: Session, user_id: str) -> bool:
    usage = get_or_create_usage(db, user_id)
    if usage.credits and usage.credits > 0:
        usage.credits -= 1; usage.last_updated = datetime.utcnow(); db.commit(); return True
    if usage.used_searches < FREE_SEARCHES:
        usage.used_searches += 1; usage.last_updated = datetime.utcnow(); db.commit(); return True
    return False

# ---------- AI filter wrapper ----------
# This function should call OpenAI (or your model) to clean, rank and standardize leads.
# Replace openai usage with your configured approach (you already had OpenAI key).
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")

def ai_filter_and_rank_leads(leads: list, context: dict = None) -> list:
    """
    Input: raw leads (list of dicts)
    Output: cleaned, deduped, ranked leads (list)
    - Keeps important fields: title, price, link, contact, snippet, source
    """
    if not leads:
        return []
    # lightweight local cleaning first
    cleaned = []
    seen_urls = set()
    for r in leads:
        url = (r.get("link") or r.get("url") or "")[:512]
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        cleaned.append({
            "title": r.get("title") or r.get("name") or "",
            "price": r.get("price") or r.get("budget") or "",
            "link": url,
            "raw": r
        })
    # For ranking / enrich we call the model with a small prompt (keep small or skip for high speed)
    try:
        prompt = "Rank and return top 10 leads by relevance. Input JSON list of leads with title, price, link. Return JSON array of the same objects ordered, and add field score (0-100)."
        # Keep prompt minimal so model token use is low.
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":prompt},{"role":"user","content": json.dumps(cleaned[:30])}],
            max_tokens=512
        )
        text = resp.choices[0].message["content"]
        parsed = json.loads(text)
        # ensure safe format fallback
        if isinstance(parsed, list):
            return parsed
    except Exception as e:
        # if AI fails, fallback to cleaned list
        print("AI filter failed:", e)
    return cleaned

# ---------- DB save helpers (unchanged) ----------
def save_buyer_results(user_id: str, results: list):
    db = SessionLocal()
    try:
        for r in results:
            entry = BuyerLead(user_id=user_id, title=r.get("title",""), price=r.get("price",""), link=r.get("link"), raw=json.dumps(r))
            db.add(entry)
        db.commit()
    finally:
        db.close()

def save_seller_results(user_id: str, results: list):
    db = SessionLocal()
    try:
        for r in results:
            entry = SellerLead(user_id=user_id, title=r.get("title",""), link=r.get("link"), raw=json.dumps(r))
            db.add(entry)
        db.commit()
    finally:
        db.close()

def save_social_results(user_id: str, platform: str, results: list):
    db = SessionLocal()
    try:
        for r in results:
            entry = SocialLead(user_id=user_id, platform=platform, title=r.get("title",""), link=r.get("link"), raw=json.dumps(r))
            db.add(entry)
        db.commit()
    finally:
        db.close()

def save_universal_scrape(user_id: str, payload: dict):
    db = SessionLocal()
    try:
        entry = UniversalScrape(user_id=user_id, source_url=payload.get("source_url"), page_title=payload.get("page_title"), preview_text=payload.get("preview_text"), raw=json.dumps(payload))
        db.add(entry)
        db.commit()
    finally:
        db.close()

# ---------- Routes ----------

@app.get("/")
def root():
    return {"message":"Nest Realtor API running"}

# Property on-demand endpoint (user asks => trigger property API scraper)
@app.post("/scrape/property")
async def scrape_property(request: Request, background: BackgroundTasks):
    user_id = _validate_supabase_token(request)
    body = await request.json()
    location = body.get("location","").strip()
    limit = int(body.get("limit") or 20)
    db = SessionLocal()
    try:
        allowed = consume_credit_or_free(db, user_id)
        if not allowed:
            raise HTTPException(status_code=402, detail="No free searches left")
        # call your property bot - try multiple names
        resp = None
        for fn in ("search_property24","search_property_api","search_buyer_leads","search_property"):
            fn_obj = getattr(bots, fn, None)
            if callable(fn_obj):
                try:
                    resp = fn_obj(location, limit)
                    break
                except Exception:
                    continue
        if not resp:
            raise HTTPException(status_code=500, detail="No property bot available")
        if resp.get("status") != "success":
            raise HTTPException(status_code=500, detail=resp)
        raw_results = resp.get("results", [])[:limit]
        filtered = ai_filter_and_rank_leads(raw_results, {"type":"property","location":location})
        # save in background
        background.add_task(save_buyer_results, user_id, filtered)
        return {"status":"ok","count":len(filtered),"results":filtered}
    finally:
        db.close()

# Social Leads System (SLS) on-demand endpoint
@app.post("/scrape/social")
async def scrape_social(request: Request, background: BackgroundTasks):
    user_id = _validate_supabase_token(request)
    body = await request.json()
    platform = (body.get("platform") or "instagram").lower()
    query = body.get("query","").strip()
    limit = int(body.get("limit") or 20)
    db = SessionLocal()
    try:
        allowed = consume_credit_or_free(db, user_id)
        if not allowed:
            raise HTTPException(status_code=402, detail="No free searches left")
        # call social bot candidate functions
        resp = None
        for fn in ("social_media_leads","generic_social_search","facebook_public_search","search_social"):
            fn_obj = getattr(bots, fn, None)
            if callable(fn_obj):
                try:
                    resp = fn_obj(query, platform)  # some functions signature may differ
                    break
                except TypeError:
                    # try flexible call
                    try:
                        resp = fn_obj({"query":query,"platform":platform,"limit":limit})
                        break
                    except Exception:
                        continue
                except Exception:
                    continue
        if not resp:
            raise HTTPException(status_code=500, detail="No social bot available")
        if resp.get("status") != "success":
            raise HTTPException(status_code=500, detail=resp)
        raw_results = resp.get("results", [])[:limit]
        filtered = ai_filter_and_rank_leads(raw_results, {"type":"social","platform":platform,"query":query})
        background.add_task(save_social_results, user_id, platform, filtered)
        return {"status":"ok","count":len(filtered),"results":filtered}
    finally:
        db.close()
