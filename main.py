# main.py
import os
from dotenv import load_dotenv
import json
import requests
from typing import List
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

# local modules
import bots
from database import SessionLocal, Base, engine, BuyerLead, SellerLead, SocialLead, UniversalScrape, PaymentRecord, UserUsage
from config import SUPABASE_URL, SUPABASE_KEY

# Load .env
load_dotenv()

# FastAPI app
app = FastAPI(title="Nest Realtor — Minimal Backend (Option A)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create DB tables
Base.metadata.create_all(bind=engine)

FREE_SEARCHES = 5

# ---------------------------------
# Helpers
# ---------------------------------
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
            data = r.json()
            user_id = data.get("id")
            return user_id
    except Exception:
        pass
    raise HTTPException(status_code=401, detail="Invalid Supabase token")

from sqlalchemy.orm import Session

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

# Background DB save helpers
def save_buyer_results(user_id: str, results: list):
    db = SessionLocal()
    try:
        for r in results:
            entry = BuyerLead(
                user_id=user_id,
                title=r.get("title") or r.get("name") or "",
                price=r.get("price") or r.get("budget") or "",
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
                title=r.get("title") or "",
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
                title=r.get("title") or r.get("profile") or "",
                link=r.get("link"),
                raw=json.dumps(r)
            )
            db.add(entry)
        db.commit()
    finally:
        db.close()

def save_universal_scrape(user_id: str, payload: dict):
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

# ---------------------------------
# Routes
# ---------------------------------
@app.get("/")
def root():
    return {"message": "Nest Realtor API is running 🚀"}

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

@app.post("/buyer-leads")
async def buyer_leads(request: Request, background: BackgroundTasks):
    user_id = _validate_supabase_token(request)
    body = await request.json()
    location = body.get("location", "").strip()
    min_price = int(body.get("min_price") or 0)
    max_price = int(body.get("max_price") or 0)
    limit = int(body.get("limit") or 10)

    db = SessionLocal()
    try:
        allowed = consume_credit_or_free(db, user_id)
        if not allowed:
            raise HTTPException(status_code=402, detail="No free searches left — please purchase credits")

        resp = bots.search_property24(location, limit)
        if resp.get("status") != "success":
            return {"status": "error", "detail": resp}
        results = resp.get("results", [])[:limit]

        background.add_task(save_buyer_results, user_id, results)
        return {"status": "ok", "count": len(results), "results": results}
    finally:
        db.close()

@app.post("/seller-leads")
async def seller_leads(request: Request, background: BackgroundTasks):
    user_id = _validate_supabase_token(request)
    body = await request.json()
    location = body.get("location", "").strip()
    limit = int(body.get("limit") or 10)

    db = SessionLocal()
    try:
        allowed = consume_credit_or_free(db, user_id)
        if not allowed:
            raise HTTPException(status_code=402, detail="No free searches left — please purchase credits")

        resp = bots.search_gumtree(location, limit)
        if resp.get("status") != "success":
            return {"status": "error", "detail": resp}
        results = resp.get("results", [])[:limit]

        background.add_task(save_seller_results, user_id, results)
        return {"status": "ok", "count": len(results), "results": results}
    finally:
        db.close()

@app.post("/social-leads")
async def social_leads(request: Request, background: BackgroundTasks):
    user_id = _validate_supabase_token(request)
    body = await request.json()
    platform = (body.get("platform") or "instagram").lower()
    query = body.get("query", "")
    limit = int(body.get("limit") or 10)

    db = SessionLocal()
    try:
        allowed = consume_credit_or_free(db, user_id)
        if not allowed:
            raise HTTPException(status_code=402, detail="No free searches left — please purchase credits")

        resp = bots.facebook_public_search(query, limit) if platform == "facebook" else bots.generic_social_search(query, platform, limit)
        if resp.get("status") != "success":
            return {"status": "error", "detail": resp}
        results = resp.get("results", [])[:limit]

        background.add_task(save_social_results, user_id, platform, results)
        return {"status": "ok", "count": len(results), "results": results}
    finally:
        db.close()

@app.post("/universal-scrape")
async def universal_scrape(request: Request, background: BackgroundTasks):
    user_id = _validate_supabase_token(request)
    body = await request.json()
    url = body.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="url required")

    resp = bots.universal_scrape(url)
    if resp.get("status") != "success":
        return {"status": "error", "detail": resp}
    background.add_task(save_universal_scrape, user_id, resp)
    return {"status": "ok", "result": resp}

@app.post("/confirm-payment")
async def confirm_payment(request: Request):
    body = await request.json()
    user_id = body.get("user_id")
    amount = int(body.get("amount", 0))
    provider = body.get("provider", "yoco")
    metadata = body.get("metadata", {})

    if not user_id or amount <= 0:
        raise HTTPException(status_code=400, detail="user_id and positive amount required")

    if amount >= 5499:
        credits = 60
    elif amount >= 3299:
        credits = 40
    elif amount >= 2599:
        credits = 30
    elif amount >= 1799:
        credits = 20
    else:
        credits = max(5, amount // 100)

    db = SessionLocal()
    try:
        usage = db.query(UserUsage).filter(UserUsage.user_id == user_id).first()
        if not usage:
            usage = UserUsage(user_id=user_id, used_searches=0, credits=credits)
            db.add(usage)
        else:
            usage.credits = (usage.credits or 0) + credits
            usage.last_updated = datetime.utcnow()

        pay = PaymentRecord(user_id=user_id, amount=amount, provider=provider, metadata=json.dumps(metadata))
        db.add(pay)
        db.commit()
        return {"status": "ok", "added_credits": credits, "total_credits": usage.credits}
    finally:
        db.close()

@app.get("/usage")
def get_usage(request: Request):
    user_id = _validate_supabase_token(request)
    db = SessionLocal()
    try:
        usage = db.query(UserUsage).filter(UserUsage.user_id == user_id).first()
        if not usage:
            return {"user_id": user_id, "used_searches": 0, "credits": 0}
        return {"user_id": user_id, "used_searches": usage.used_searches, "credits": usage.credits}
    finally:
        db.close()

@app.get("/leads")
def get_user_leads(request: Request, page: int = 1, per_page: int = 20):
    user_id = _validate_supabase_token(request)
    db = SessionLocal()
    try:
        offset = (page - 1) * per_page
        buyers = db.query(BuyerLead).filter(BuyerLead.user_id == user_id).order_by(BuyerLead.created_at.desc()).offset(offset).limit(per_page).all()
        sellers = db.query(SellerLead).filter(SellerLead.user_id == user_id).order_by(SellerLead.created_at.desc()).offset(offset).limit(per_page).all()
        socials = db.query(SocialLead).filter(SocialLead.user_id == user_id).order_by(SocialLead.created_at.desc()).offset(offset).limit(per_page).all()
        universal = db.query(UniversalScrape).filter(UniversalScrape.user_id == user_id).order_by(UniversalScrape.created_at.desc()).offset(offset).limit(per_page).all()

        def serialize(obj):
            return {
                "type": obj.__class__.__name__,
                "id": obj.id,
                "created_at": obj.created_at.isoformat(),
                "title": getattr(obj, "title", None) or getattr(obj, "page_title", None) or "",
                "link": getattr(obj, "link", None) or getattr(obj, "source_url", None),
                "raw": json.loads(obj.raw) if obj.raw else None
            }

        items = [serialize(x) for x in (buyers + sellers + socials + universal)]
        items.sort(key=lambda i: i["created_at"], reverse=True)
        return {"status": "ok", "count": len(items), "page": page, "per_page": per_page, "results": items}
    finally:
        db.close()
