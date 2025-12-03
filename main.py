# main.py — Full Nest Realtor Backend

import os
import json
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

import requests
import openai

# Local modules
import bots
from database import (
    SessionLocal, Base, engine,
    BuyerLead, SellerLead, SocialLead,
    UniversalScrape, PaymentRecord, UserUsage
)
from config import SUPABASE_URL, SUPABASE_KEY

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI(
    title="Nest Realtor — Combined Backend (Property + SLS)",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

FREE_SEARCHES = 5

from sqlalchemy.orm import Session

# -------------------------------------------------------------------
#                       HELPERS
# -------------------------------------------------------------------

def _validate_supabase_token(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = header.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    # If Supabase URL exists, validate token
    if SUPABASE_URL:
        try:
            r = requests.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={"Authorization": f"Bearer {token}"},
                timeout=8
            )
            if r.status_code == 200:
                data = r.json()
                uid = data.get("id")
                if uid:
                    return uid
        except Exception:
            pass

    # fallback: treat token as user_id (dev mode)
    return token


def get_or_create_usage(db: Session, user_id: str):
    usage = db.query(UserUsage).filter(UserUsage.user_id == user_id).first()
    if usage:
        return usage

    usage = UserUsage(user_id=user_id, used_searches=0, credits=0)
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage


def consume_credit_or_free(db: Session, user_id: str) -> bool:
    usage = get_or_create_usage(db, user_id)

    if usage.credits > 0:
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

    # Optional AI Ranking
    try:
        if openai.api_key and len(cleaned) > 0:
            prompt = "Rank these leads by relevance (0-100). Return JSON array of objects with original fields plus score."
            resp = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(cleaned[:30])}
                ],
                max_tokens=512
            )
            text = resp.choices[0].message["content"]
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
    except Exception:
        pass

    return cleaned


# -------------------------------------------------------------------
#                       DB SAVE HELPERS
# -------------------------------------------------------------------

def save_buyer_results(user_id: str, results: list):
    db = SessionLocal()
    try:
        for r in results:
            entry = BuyerLead(
                user_id=user_id,
                title=r.get("title", ""),
                price=r.get("price", ""),
                link=r.get("link"),
                raw=json.dumps(r)
            )
            db.add(entry)
            db.commit()
    finally:
        db.close()


def save_seller_results(user_id: str, results: list):
    db = SessionLocal()
    try:
        for r in results:
            entry = SellerLead(
                user_id=user_id,
                title=r.get("title", ""),
                link=r.get("link"),
                raw=json.dumps(r)
            )
            db.add(entry)
            db.commit()
    finally:
        db.close()


def save_social_results(user_id: str, platform: str, results: list):
    db = SessionLocal()
    try:
        for r in results:
            entry = SocialLead(
                user_id=user_id,
                platform=platform,
                title=r.get("title", ""),
                link=r.get("link"),
                raw=json.dumps(r)
            )
            db.add(entry)
            db.commit()
    finally:
        db.close()


def save_universal(user_id: str, payload: dict):
    db = SessionLocal()
    try:
        entry = UniversalScrape(
            user_id=user_id,
            source_url=payload.get("source_url"),
            page_title=payload.get("page_title"),
            preview_text=payload.get("preview_text"),
            raw=json.dumps(payload)
        )
        db.add(entry)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------
#                       ROOT + HEALTH
# -------------------------------------------------------------------

@app.get("/")
def root():
    return {"status": "ok", "message": "Nest Realtor Backend Running"}


# -------------------------------------------------------------------
#                       AI FILTER
# -------------------------------------------------------------------

@app.post("/ai-filter")
async def ai_filter(request: Request):
    body = await request.json()
    leads = body.get("leads", [])
    context = body.get("context", {})
    filtered = ai_filter_and_rank_leads(leads, context)
    return {"status": "ok", "count": len(filtered), "results": filtered}


# -------------------------------------------------------------------
#                       SOCIAL SCRAPING
# -------------------------------------------------------------------

@app.post("/scrape/social")
async def scrape_social(request: Request, background: BackgroundTasks):
    user_id = _validate_supabase_token(request)
    body = await request.json()

    platform = (body.get("platform") or "instagram").lower()
    query = body.get("query", "").strip()
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
        filtered = ai_filter_and_rank_leads(
            raw,
            {"type": "social", "platform": platform, "query": query}
        )

        background.add_task(save_social_results, user_id, platform, filtered)
        return {"status": "ok", "count": len(filtered), "results": filtered}

    finally:
        db.close()


# -------------------------------------------------------------------
#                  DASHBOARD LEAD GENERATION ENDPOINTS
# -------------------------------------------------------------------

@app.post("/generate-lead")
async def generate_lead(request: Request):
    user_id = _validate_supabase_token(request)
    body = await request.json()

    try:
        lead = await bots.generate_lead(user_id, body)
        return {"status": "ok", "lead": lead}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/store-lead")
async def store_lead(request: Request):
    user_id = _validate_supabase_token(request)
    body = await request.json()

    try:
        await bots.store_lead(user_id, body)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/leads")
async def get_leads(request: Request):
    user_id = _validate_supabase_token(request)

    db = SessionLocal()
    try:
        buyer = db.query(BuyerLead).filter(BuyerLead.user_id == user_id).all()
        seller = db.query(SellerLead).filter(SellerLead.user_id == user_id).all()
        social = db.query(SocialLead).filter(SocialLead.user_id == user_id).all()

        return {
            "status": "ok",
            "buyer_leads": [json.loads(l.raw) for l in buyer],
            "seller_leads": [json.loads(l.raw) for l in seller],
            "social_leads": [json.loads(l.raw) for l in social]
        }

    finally:
        db.close()


# -------------------------------------------------------------------
#                       WEBHOOK
# -------------------------------------------------------------------

@app.post("/webhook")
async def webhook_handler(request: Request, background: BackgroundTasks):
    body = await request.json()
    user_id = body.get("user_id", "unknown")

    background.add_task(save_universal, user_id, body)
    return {"status": "ok", "received": body}
