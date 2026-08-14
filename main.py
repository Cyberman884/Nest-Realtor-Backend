import os
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from lead_engine import generate_leads as run_lead_engine
from supabase_client import supabase

# --------------------------------------------------
# ENV
# --------------------------------------------------
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nest-realtor")

# --------------------------------------------------
# APP
# --------------------------------------------------
app = FastAPI(title="Nest Realtor Backend", version="5.1.0"
)
@app.get("/test-supabase")
async def test_supabase():

    result = supabase.table("opportunities").select("*").limit(1).execute()

    return {
        "success": True,
        "records_found": len(result.data)
    }
# --------------------------------------------------
# ✅ CORS FIX (THIS IS WHAT YOU WERE MISSING)
# --------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all (safe for demo)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# MODEL
# --------------------------------------------------
class LeadRequest(BaseModel):
    query: str
    location: str
    user_id: str

# --------------------------------------------------
# ROOT
# --------------------------------------------------
@app.get("/")
def root():
    return {"status": "Nest Realtor backend running 🚀"}

# --------------------------------------------------
# 🚀 LEADS ENDPOINT
# --------------------------------------------------
@app.post("/leads")
def generate_leads_endpoint(payload: LeadRequest):

    try:

        print("🔥 /leads endpoint triggered")

        # ----------------------------------------
        # VALIDATION
        # ----------------------------------------

        if not payload.location:
            return {
                "success": False,
                "error": "Location is required"
            }

        if not payload.user_id:
            return {
                "success": False,
                "error": "Missing user_id"
            }

        print(f"👤 User: {payload.user_id}")
        print(f"📍 Query: {payload.query}")
        print(f"📍 Location: {payload.location}")

        # ----------------------------------------
        # DEMO LIMIT
        # ----------------------------------------

        DEMO_LIMIT = 2

        # ----------------------------------------
        # RUN LEAD ENGINE
        # ----------------------------------------

        result = run_lead_engine(
            query=payload.query,
            location=payload.location
        )

        if not result.get("success"):
            return result

        leads = result.get("leads", [])

        leads = leads[:DEMO_LIMIT]

        leads_count = len(leads)

        print(f"✅ Leads generated: {leads_count}")

        print("📊 Sources:", result.get("sources"))

        # ----------------------------------------
        # RESPONSE
        # ----------------------------------------

        return {
            "success": True,
            "engine": result.get("engine", "multi_source"),
            "sources": result.get(
                "sources",
                [
                    "google_places",
                    "gumtree",
                    "facebook_marketplace"
                ]
            ),
            "count": leads_count,
            "leads": leads,
            "usage": {
                "used": leads_count,
                "limit": DEMO_LIMIT,
                "remaining": max(DEMO_LIMIT - leads_count, 0)
            }
        }

    except Exception as e:

        logger.error(f"❌ Error: {e}")

        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "engine": "error",
                "sources": [],
                "count": 0,
                "leads": [],
                "error": str(e)
            }
         )
# --------------------------------------------------
# 💳 YOCO CHECKOUT
# --------------------------------------------------

@app.post("/create_checkout")
async def create_checkout(payload: dict):

    try:
        import requests

        secret_key = os.getenv("YOCO_SECRET_KEY")

        if not secret_key:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "YOCO_SECRET_KEY is missing"
                }
            )

        amount = int(payload.get("amount", 0))
        plan = payload.get("plan", "Nest Realtor")

        if amount <= 0:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Invalid payment amount"
                }
            )

        checkout_data = {
            "amount": amount,
            "currency": "ZAR",
            "successUrl": payload.get(
                "success_url",
                "https://nest-realtor.netlify.app/dashboard.html"
            ),
            "cancelUrl": payload.get(
                "cancel_url",
                "https://nest-realtor.netlify.app/pricing.html"
            ),
            "metadata": {
                "plan": plan
            }
        }

        response = requests.post(
            "https://payments.yoco.com/api/checkouts",
            headers={
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json"
            },
            json=checkout_data,
            timeout=30
        )

        print("YOCO STATUS:", response.status_code)
        print("YOCO RESPONSE:", response.text)

        if response.status_code >= 400:
            return JSONResponse(
                status_code=response.status_code,
                content={
                    "success": False,
                    "error": response.text
                }
            )

        data = response.json()

        return {
            "success": True,
            "redirectUrl": data.get("redirectUrl")
        }

    except Exception as e:

        logger.error(f"❌ Yoco checkout error: {e}")

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )

