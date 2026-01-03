 # main.py — Nest Realtor Backend (working baseline)

import os
import logging
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

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
    version="1.0.0"
)

# --------------------------------------------------
# MODELS
# --------------------------------------------------
class LeadRequest(BaseModel):
    query: str
    location: str | None = None

# --------------------------------------------------
# HEALTH
# --------------------------------------------------
@app.get("/")
def root():
    return {"status": "Nest Realtor backend running"}

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
# CORE LEAD ENGINE
# --------------------------------------------------
def google_places_leads(query: str, location: str | None):
    """
    Primary lead source using Google Places
    """
    if not GOOGLE_PLACES_API_KEY:
        raise Exception("Google API key missing")

    # Default to Sandton if no location given
    location_map = {
        "sandton": "-26.1076,28.0567",
        "johannesburg": "-26.2041,28.0473",
        "cape town": "-33.9249,18.4241",
    }

    coords = location_map.get(
        (location or "sandton").lower(),
        "-26.1076,28.0567"
    )

    url = (
        "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        f"?location={coords}"
        "&radius=15000"
        "&type=real_estate_agency"
        f"&keyword={query}"
        f"&key={GOOGLE_PLACES_API_KEY}"
    )

    response = requests.get(url, timeout=15)
    data = response.json()

    if data.get("status") != "OK":
        raise Exception(data.get("error_message", "Google Places failed"))

    leads = []
    for r in data.get("results", []):
        leads.append({
            "name": r.get("name"),
            "address": r.get("vicinity"),
            "rating": r.get("rating"),
            "user_ratings_total": r.get("user_ratings_total"),
            "source": "google_places"
        })

    return leads

# --------------------------------------------------
# LEADS ENDPOINT (THIS WAS MISSING)
# --------------------------------------------------
@app.post("/leads")
def generate_leads(payload: LeadRequest):
    try:
        leads = google_places_leads(
            query=payload.query,
            location=payload.location
        )

        if not leads:
            return {
                "success": False,
                "engine": "google_places",
                "leads": [],
                "error": "No leads found"
            }

        return {
            "success": True,
            "engine": "google_places",
            "count": len(leads),
            "leads": leads
        }

    except Exception as e:
        logger.error(f"Lead generation failed: {e}")

        # Safe fallback response (no crash)
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "engine": "fallback",
                "leads": [],
                "error": str(e)
            }
        )
