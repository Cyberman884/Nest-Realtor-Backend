# main.py — Nest Realtor Backend (stable)

import os
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# ✅ AI QUERY ROUTER (KEEP THIS)
from backend.ai.resolve_query import router as ai_router

# --------------------------------------------------
# ENV + LOGGING
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
# ROUTERS
# --------------------------------------------------
app.include_router(ai_router)

# --------------------------------------------------
# HEALTH
# --------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

# --------------------------------------------------
# DEBUG — ENV CHECK (NO QUOTA USED)
# --------------------------------------------------
@app.get("/debug/google")
def debug_google_key():
    return {
        "key_present": bool(GOOGLE_PLACES_API_KEY),
        "key_preview": GOOGLE_PLACES_API_KEY[:6] + "..." if GOOGLE_PLACES_API_KEY else None
    }

# --------------------------------------------------
# REAL GOOGLE PLACES LEAD TEST (OPTIONAL)
# --------------------------------------------------
@app.get("/debug/google-live")
def debug_google_live():
    """
    This actually calls Google.
    Use ONLY when testing.
    """
    if not GOOGLE_PLACES_API_KEY:
        return JSONResponse(
            status_code=500,
            content={"error": "Google Places API key missing"}
        )

    import requests

    url = (
        "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        "?location=-26.1076,28.0567"
        "&radius=15000"
        "&type=real_estate_agency"
        f"&key={GOOGLE_PLACES_API_KEY}"
    )

    r = requests.get(url, timeout=15)
    data = r.json()

    return {
        "status": r.status_code,
        "results_count": len(data.get("results", [])),
        "sample": data.get("results", [])[:3]
    }
