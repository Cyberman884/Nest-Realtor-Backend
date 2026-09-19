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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LeadRequest(BaseModel):
    query: str = ""
    location: str = ""
    user_id: str = ""


def normalize_search_input(query: str, location: str):

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


@app.get("/")
def root():

    return {
        "success": True,
        "message": "Nest Realtor Backend is running"
    }


@app.get("/health")
def health():

    return {
        "success": True,
        "status": "healthy"
    }


@app.post("/leads")
def generate_leads_endpoint(payload: LeadRequest):

    try:

        print("🔥 /leads endpoint triggered")

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

        print(
            f"👤 User: {payload.user_id}"
        )

        print(
            f"📥 Original Query: {payload.query}"
        )

        print(
            f"📥 Original Location: {payload.location}"
        )

        query, location = normalize_search_input(
            payload.query,
            payload.location
        )

        print(
            f"🔎 Final Query: {query}"
        )

        print(
            f"📍 Final Location: {location}"
        )

        if not location:

            return {
                "success": False,
                "error": "Could not determine location"
            }

        # This controls how many qualified
        # opportunities are displayed.
        DEMO_LIMIT = 2

        result = run_lead_engine(
            query=query,
            location=location
        )

        if not result.get("success"):

            return result

        leads = result.get(
            "leads",
            []
        )

        leads = leads[:DEMO_LIMIT]

        leads_count = len(leads)

        print(
            f"✅ Leads generated: {leads_count}"
        )

        print(
            "📊 Sources:",
            result.get("sources")
        )

        print(
            "📊 Source counts:",
            result.get("source_counts")
        )

        print(
            "📊 Filtered source counts:",
            result.get(
                "filtered_source_counts"
            )
        )

        return {

            "success": True,

            "engine": result.get(
                "engine",
                "multi_source"
            ),

            "sources": result.get(
                "sources",
                ["gumtree"]
            ),

            "source_counts": result.get(
                "source_counts",
                {}
            ),

            "filtered_source_counts": result.get(
                "filtered_source_counts",
                {}
            ),

            "requested_location": location,

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