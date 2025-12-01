from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy.orm import Session
import requests, openai, os, json
from datetime import datetime

# local imports

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
title="Nest Realtor Backend",
docs_url="/docs",
redoc_url="/redoc"
)

app.add_middleware(
CORSMiddleware,
allow_origins=["*"],
allow_methods=["*"],
allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

FREE_SEARCHES = 5

# ---------------- HELPERS ----------------

def _validate_supabase_token(request: Request):
header = request.headers.get("Authorization")
if not header:
raise HTTPException(status_code=401, detail="Missing Authorization header")
return header.replace("Bearer ", "").strip()

# ---------------- HEALTH ----------------

@app.get("/health")
def health_check():
return {"status": "ok", "service": "Nest Realtor Backend"}

@app.get("/")
def root():
return {"status": "ok", "message": "Nest Realtor Backend Running"}

# ---------------- SOCIAL SCRAPER ----------------

@app.post("/scrape/social")
async def scrape_social(request: Request, background: BackgroundTasks):
user_id = _validate_supabase_token(request)
body = await request.json()
platform = body.get("platform", "instagram").lower()
query = body.get("query", "")
limit = int(body.get("limit", 20))

```
resp = bots.social_media_leads(query, platform)
results = resp.get("results", [])[:limit]

background.add_task(save_social_results, user_id, platform, results)

return {"status": "ok", "count": len(results), "results": results}
```

# ---------------- PROPERTY SCRAPER ----------------

@app.post("/scrape")
async def scrape_property(request: Request):
user_id = _validate_supabase_token(request)
body = await request.json()

```
try:
    results = bots.property_scraper(body)
    return {"status": "ok", "results": results}
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

# ---------------- AI FILTER ----------------

@app.post("/ai-filter")
async def ai_filter(request: Request):
body = await request.json()
leads = body.get("leads", [])
return {"status": "ok", "results": leads}

# ---------------- LEAD GENERATION ----------------

@app.post("/generate-lead")
async def generate_lead(request: Request):
user_id = _validate_supabase_token(request)
body = await request.json()
lead = await bots.generate_lead(user_id, body)
return {"status": "ok", "lead": lead}

@app.post("/store-lead")
async def store_lead(request: Request):
user_id = _validate_supabase_token(request)
body = await request.json()
await bots.store_lead(user_id, body)
return {"status": "ok"}

@app.get("/leads")
async def get_leads(request: Request):
user_id = _validate_supabase_token(request)
db = SessionLocal()

```
buyer = db.query(BuyerLead).filter(BuyerLead.user_id == user_id).all()
seller = db.query(SellerLead).filter(SellerLead.user_id == user_id).all()
social = db.query(SocialLead).filter(SellerLead.user_id == user_id).all()

db.close()

return {
    "status": "ok",
    "buyer_leads": [json.loads(l.raw) for l in buyer],
    "seller_leads": [json.loads(l.raw) for l in seller],
    "social_leads": [json.loads(l.raw) for l in social]
}
```
