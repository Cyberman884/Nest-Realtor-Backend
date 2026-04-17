import os
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from lead_engine import generate_leads as run_lead_engine

# ✅ Supabase
from supabase import create_client, Client

# --------------------------------------------------
# ENV
# --------------------------------------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nest-realtor")

# --------------------------------------------------
# APP
# --------------------------------------------------
app = FastAPI(title="Nest Realtor Backend", version="5.0.0")

# --------------------------------------------------
# MODEL
# --------------------------------------------------
class LeadRequest(BaseModel):
    query: str
    location: str
    user_id: str  # REQUIRED

# --------------------------------------------------
# ROOT
# --------------------------------------------------
@app.get("/")
def root():
    return {"status": "Nest Realtor backend running 🚀"}

# --------------------------------------------------
# 🚀 LEADS ENDPOINT WITH FULL CONTROL
# --------------------------------------------------
@app.post("/leads")
def generate_leads_endpoint(payload: LeadRequest):
    try:
        print("🔥 /leads endpoint triggered")

        # ----------------------------------------
        # 1. FETCH USER
        # ----------------------------------------
        user_res = supabase.table("users").select("*").eq("id", payload.user_id).execute()

        if not user_res.data:
            return {
                "success": False,
                "error": "User not found"
            }

        user = user_res.data[0]

        plan = user.get("plan", "free")
        leads_used = user.get("leads_used", 0)

        # ----------------------------------------
        # 2. PLAN LIMITS (MATCH YOUR PRICING)
        # ----------------------------------------
        if plan == "free":
            lead_limit = 2
        elif plan == "starter":
            lead_limit = 20
        elif plan == "pro":
            lead_limit = 50
        elif plan == "elite":
            lead_limit = 80
        else:
            lead_limit = 0

        print(f"👤 User: {payload.user_id}")
        print(f"📦 Plan: {plan}")
        print(f"📊 Usage: {leads_used}/{lead_limit}")

        # ----------------------------------------
        # 3. BLOCK IF LIMIT REACHED
        # ----------------------------------------
        if leads_used >= lead_limit:
            return {
                "success": False,
                "engine": "limit_block",
                "leads": [],
                "error": "You’ve reached your lead limit. Upgrade your plan to continue."
            }

        # ----------------------------------------
        # 4. GENERATE LEADS
        # ----------------------------------------
        result = run_lead_engine(
            query=payload.query,
            location=payload.location
        )

        if not result.get("success"):
            return result

        leads = result.get("leads", [])
        leads_count = len(leads)

        # ----------------------------------------
        # 5. PREVENT OVER-CONSUMPTION
        # ----------------------------------------
        remaining = lead_limit - leads_used

        if leads_count > remaining:
            leads = leads[:remaining]
            leads_count = len(leads)

        # ----------------------------------------
        # 6. UPDATE USAGE
        # ----------------------------------------
        new_usage = leads_used + leads_count

        supabase.table("users").update({
            "leads_used": new_usage
        }).eq("id", payload.user_id).execute()

        print(f"✅ Updated usage: {new_usage}")

        # ----------------------------------------
        # 7. RETURN RESPONSE
        # ----------------------------------------
        return {
            "success": True,
            "engine": "google_places",
            "leads": leads,
            "count": leads_count,
            "usage": {
                "used": new_usage,
                "limit": lead_limit,
                "remaining": lead_limit - new_usage
            }
        }

    except Exception as e:
        logger.error(f"❌ Error: {e}")

        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "engine": "error",
                "leads": [],
                "error": str(e)
            }
        )