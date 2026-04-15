# main.py — FINAL WORKING VERSION

import os
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# ✅ IMPORT YOUR LEAD ENGINE
from lead_engine import generate_leads as run_lead_engine

# --------------------------------------------------
# ENV & LOGGING
# --------------------------------------------------
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nest-realtor")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    logger.info("✅ Google API key loaded")
else:
    logger.warning("⚠️ Google API key NOT found")

# --------------------------------------------------
# APP
# --------------------------------------------------
app = FastAPI(
    title="Nest Realtor Backend",
    version="3.0.0"
)

# --------------------------------------------------
# MODELS
# --------------------------------------------------
class LeadRequest(BaseModel):
    query: str
    location: str   # ✅ FIXED: now required

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
# DEBUG
# --------------------------------------------------
@app.get("/debug/google")
def debug_google_key():
    return {
        "key_present": bool(GOOGLE_API_KEY),
        "key_preview": GOOGLE_API_KEY[:6] + "..." if GOOGLE_API_KEY else None
    }

# --------------------------------------------------
# 🚀 LEADS ENDPOINT
# --------------------------------------------------
@app.post("/leads")
def generate_leads_endpoint(payload: LeadRequest):
    try:
        print("🔥 /leads endpoint triggered")
        print(f"📍 Query: {payload.query}")
        print(f"📍 Location: {payload.location}")

        result = run_lead_engine(
            query=payload.query,
            location=payload.location
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