import os
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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
        print(f"📍 Location: {payload.location}")

        # ----------------------------------------
        # DEMO LIMIT
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

        leads = result.get("leads", [])[:DEMO_LIMIT]
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