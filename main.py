# main.py — FINAL CONNECTED VERSION

import os
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# ✅ IMPORT YOUR REAL ENGINE
from lead_engine import generate_leads as run_lead_engine

# --------------------------------------------------
# ENV & LOGGING
# --------------------------------------------------
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nest-realtor")

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

if GOOGLE_PLACES_API_KEY:
    logger.info("✅ Google Places API key loaded")
else:
    logger.warning("⚠️ Google Places API key NOT found")

# --------------------------------------------------
# APP
# --------------------------------------------------
app = FastAPI(
    title="Nest Realtor Backend",
    version="2.0.0"
)

# --------------------------------------------------
# MODELS
# --------------------------------------------------
class LeadRequest(BaseModel):
    query: str

# --------------------------------------------------
# HEALTH
# --------------------------------------------------
@app.get("/")
def root():
    return {"status": "Nest Realtor backend running 🚀"}

@app.get("/health")
def health():
    return {"status": "ok"}

# --------------------------------------------------
# DEBUG — CHECK ENV
# --------------------------------------------------
@app.get("/debug/google")
def debug_google_key():
    return {
        "key_present": bool(GOOGLE_PLACES_API_KEY),
        "key_preview": GOOGLE_PLACES_API_KEY[:6] + "..." if GOOGLE_PLACES_API_KEY else None
    }

# --------------------------------------------------
# 🚀 MAIN LEADS ENDPOINT (CONNECTED TO REAL ENGINE)
# --------------------------------------------------
@app.post("/leads")
def generate_leads_endpoint(payload: LeadRequest):
    try:
        print("🔥 /leads endpoint triggered")

        result = run_lead_engine(
            query=payload.query
        )

        return result

    except Exception as e:
        logger.error(f"Lead generation failed: {e}")

        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "engine": "fallback",
                "leads": [],
                "error": str(e)
            }
        )