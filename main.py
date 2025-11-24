# main.py — Combined backend with combined leads endpoint (property + SLS)
import os
import json
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

import requests  # ensure present
import openai

# local modules
import bots
from database import SessionLocal, Base, engine, BuyerLead, SellerLead, SocialLead, UniversalScrape, PaymentRecord, UserUsage
from config import SUPABASE_URL, SUPABASE_KEY

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI(
    title="Nest Realtor — Combined Backend (Property + SLS)",
    docs_url="/docs",
    redoc_url="/redoc"
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

Base.metadata.create_all(bind=engine)

FREE_SEARCHES = 5

from sqlalchemy.orm import Session

def _validate_supabase_token(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = header.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    # Try Supabase user endpoint
    if SUPABASE_URL:
        try:
            r = requests.get(f"{SUPABASE_URL}/auth/v1/user", headers={"Authorization": f"Bearer {token}"}, timeout=8)
            if r.status_code == 200:
                data = r.json()
                uid = data.get("id")
                if uid:
                    return uid
        except Exception:
            pass
    # Fallback: return token as user id for dev/testing (NOT for prod)
    return token

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

# AI filter (simple, safe fallback)
def ai_filter_and_rank_leads(leads: list, context: dict = None) -> list:
    if not leads:
        return []
    cleaned = []
    seen = set()
    for r in leads:
        link = (r.get("link") or r.get("url") or "")[:512]
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
    # try light OpenAI enrichment (optional)
    try:
        # small prompt only if OPENAI key exists
        if openai.api_key and len(cleaned) > 0:
            prompt = "Rank these leads by relevance (0-100). Return JSON array of objects with original fields plus score."
            resp = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":prompt},{"role":"user","content": json.dumps(cleaned[:30])}],
                max_tokens=512
            )
            text = resp.choices[0].message["content"]
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
    except Exception:
        pass
    return cleaned

# DB save helpers
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

def save_universal(user_id: str, payload: dict):
    db = SessionLocal()
    try:
        entry = UniversalScrape(user_id=user_id, source_url=payload.get("source_url"), page_title=payload.get("page_title"), preview_text=payload.get("preview_text"), raw=json.dumps(payload))
        db.add(entry)
        db.commit()
    finally:
        db.close()

# Routes
@app.get("/")
def root():
    return {"message":"Nest Realtor API running"}

@app.get("/health")
def health():
    return {"status":"ok", "time": datetime.utcnow().isoformat()}

# Combined endpoint: returns property leads + social leads together
@app.post("/scrape/combined")
async def scrape_combined(request: Request, background: BackgroundTasks):
    user_id = _validate_supabase_token(request)
    body = await request.json()
    location = body.get("location","").strip()
    query = body.get("query", "") or location
    limit = int(body.get("limit") or 20)

    db = SessionLocal()
    try:
        allowed = consume_credit_or_free(db, user_id)
        if not allowed:
            raise HTTPException(status_code=402, detail="No free searches left — purchase credits")

        # 1) property leads (buyer + seller)
        prop_resp = None
        for fn in ("search_buyer_leads","search_property24","search_property"):
            fn_obj = getattr(bots, fn, None)
            if callable(fn_obj):
                try:
                    prop_resp = fn_obj(location, limit)
                    break
                except Exception:
                    continue
        prop_results = []
        if prop_resp and prop_resp.get("status") == "success":
            prop_results = prop_resp.get("results", [])[:limit]
        # 2) social leads (multi-platform)
        social_results = []
        platforms = ["instagram","facebook","tiktok","linkedin","twitter"]
        for p in platforms:
            try:
                resp = bots.social_media_leads(query, p)
                if resp and resp.get("status") == "success":
                    social_results.extend(resp.get("results", [])[:limit])
            except Exception:
                continue

        # apply AI filter & ranking
        combined_raw = (prop_results[:limit] if prop_results else []) + (social_results[:limit] if social_results else [])
        filtered = ai_filter_and_rank_leads(combined_raw, {"type":"combined","location":location, "query": query})

        # split and save: where platform/source indicates social vs property
        props_to_save = [r for r in filtered if r.get("platform") in ("property24","gumtree","unknown") or r.get("raw", {}).get("source") in ("property24","gumtree")]
        socials_to_save = [r for r in filtered if r.get("platform") not in ("property24","gumtree")]

        # background saves
        background.add_task(save_buyer_results, user_id, props_to_save)
        background.add_task(save_social_results, user_id, "combined", socials_to_save)

        return {"status":"ok", "count": len(filtered), "results": filtered}
    finally:
        db.close()

# legacy endpoints (kept for compatibility)
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
        resp = bots.search_buyer_leads(location, limit)
        if not resp or resp.get("status") != "success":
            raise HTTPException(status_code=500, detail=resp)
        raw = resp.get("results", [])[:limit]
        filtered = ai_filter_and_rank_leads(raw, {"type":"property","location":location})
        background.add_task(save_buyer_results, user_id, filtered)
        return {"status":"ok","count":len(filtered),"results":filtered}
    finally:
        db.close()

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
        resp = bots.social_media_leads(query, platform)
        if not resp or resp.get("status") != "success":
            raise HTTPException(status_code=500, detail=resp)
        raw = resp.get("results", [])[:limit]
        filtered = ai_filter_and_rank_leads(raw, {"type":"social","platform":platform,"query":query})
        background.add_task(save_social_results, user_id, platform, filtered)
        return {"status":"ok","count":len(filtered),"results":filtered}
    finally:
        db.close()
