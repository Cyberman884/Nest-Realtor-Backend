import logging
import re

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from lead_engine import generate_leads as run_lead_engine


app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class LeadRequest(BaseModel):
    query: str = ""
    location: str = ""
    user_id: str = ""


# ============================================================
# SEARCH INPUT NORMALIZER
# ============================================================

def normalize_search_input(query: str, location: str):
    """
    Fixes cases where the frontend sends the entire search phrase
    inside the location field.

    Example:

        query = ""
        location = "Houses for sale in Pretoria"

    Becomes:

        query = "Houses for sale"
        location = "Pretoria"
    """

    query = (query or "").strip()
    location = (location or "").strip()

    if not location:
        return query, location

    match = re.match(
        r"^(.*?)\s+in\s+(.+)$",
        location,
        flags=re.IGNORECASE
    )

    if match:
        possible_query = match.group(1).strip()
        possible_location = match.group(2).strip()

        search_words = [
            "house",
            "houses",
            "home",
            "homes",
            "property",
            "properties",
            "flat",
            "flats",
            "apartment",
            "apartments",
            "land",
            "plot",
            "plots",
            "commercial",
            "farm",
            "farms",
            "sale",
            "selling"
        ]

        if any(
            word in possible_query.lower()
            for word in search_words
        ):
            if not query:
                query = possible_query

            location = possible_location

    return query, location


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "success": True,
        "message": "Nest Realtor Backend is running"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return {
        "success": True,
        "status": "healthy"
    }


# ============================================================
# LEADS ENDPOINT
# ============================================================

@app.post("/leads")
def generate_leads_endpoint(payload: LeadRequest):

    try:
        print("🔥 /leads endpoint triggered")

        # ----------------------------------------------------
        # BASIC VALIDATION
        # ----------------------------------------------------

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
        print(f"📥 Original Query: {payload.query}")
        print(f"📥 Original Location: {payload.location}")

        # ----------------------------------------------------
        # NORMALIZE QUERY + LOCATION
        # ----------------------------------------------------

        query, location = normalize_search_input(
            payload.query,
            payload.location
        )

        print(f"🔎 Final Query: {query}")
        print(f"📍 Final Location: {location}")

        if not location:
            return {
                "success": False,
                "error": "Could not determine location"
            }

        # ----------------------------------------------------
        # DEMO LIMIT
        # ----------------------------------------------------

        DEMO_LIMIT = 2

        # ----------------------------------------------------
        # RUN LEAD ENGINE
        # ----------------------------------------------------

        result = run_lead_engine(
            query=query,
            location=location
        )

        if not result.get("success"):
            return result

        # ----------------------------------------------------
        # GET LEADS
        # ----------------------------------------------------

        leads = result.get("leads", [])

        # Keep the free/demo response limited.
        leads = leads[:DEMO_LIMIT]

        leads_count = len(leads)

        print(f"✅ Leads generated: {leads_count}")
        print("📊 Sources:", result.get("sources"))

        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return {
            "success": True,

            "engine": result.get(
                "engine",
                "multi_source"
            ),

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

            "search": {
                "query": query,
                "location": location
            },

            "usage": {
                "used": leads_count,
                "limit": DEMO_LIMIT,
                "remaining": max(
                    DEMO_LIMIT - leads_count,
                    0
                )
            }
        }

    except Exception as e:

        logger.error(
            f"❌ Error: {e}",
            exc_info=True
        )

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