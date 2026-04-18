import os
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from lead_engine import generate_leads as run_lead_engine

# --------------------------------------------------
# ENV
# --------------------------------------------------
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nest-realtor")

# --------------------------------------------------
# APP
# --------------------------------------------------
app = FastAPI(title="Nest Realtor Backend", version="5.1.0")

# --------------------------------------------------
# MODEL
# --------------------------------------------------
class LeadRequest(BaseModel):
    query: str
    location: str
    user_id: str  # still required for tracking later

# --------------------------------------------------
# ROOT
# --------------------------------------------------
@app.get("/")
def root():
    return {"status": "Nest Realtor backend running 🚀"}

# --------------------------------------------------
# 🚀 LEADS ENDPOINT (DEMO MODE - NO DB REQUIRED)
# --------------------------------------------------
@app.post("/leads")
def generate_leads_endpoint(payload: LeadRequest):
    try:
        print("🔥 /leads endpoint triggered")

        # ----------------------------------------
        # BASIC VALIDATION
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
        print(f"📍 Location: {payload.location}")

        # ----------------------------------------
        # TEMP DEMO LIMIT (2 leads max)
        # ----------------------------------------
        DEMO_LIMIT = 2

        # ----------------------------------------
        # GENERATE LEADS
        # ----------------------------------------
        result = run_lead_engine(
            query=payload.query,
            location=payload.location
        )

        if not result.get("success"):
            return result

        leads = result.get("leads", [])

        # ----------------------------------------
        # LIMIT RESULTS (DEMO MODE)
        # ----------------------------------------
        leads = leads[:DEMO_LIMIT]
        leads_count = len(leads)

        print(f"✅ Leads generated: {leads_count}")

        # ----------------------------------------
        # RESPONSE
        # ----------------------------------------
        return {
            "success": True,
            "engine": "google_places",
            "leads": leads,
            "count": leads_count,
            "usage": {
                "used": leads_count,
                "limit": DEMO_LIMIT,
                "remaining": 0
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