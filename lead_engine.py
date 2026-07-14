import os
import requests
from typing import Dict

from filter_leads import filter_leads
from marketplace_urls import (
    GUMTREE_URLS,
    FACEBOOK_MARKETPLACE_URLS
)
from gumtree import search_gumtree
from facebook_marketplace import get_facebook_marketplace

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


def get_place_details(place_id):
    try:
        url = "https://maps.googleapis.com/maps/api/place/details/json"

        params = {
            "place_id": place_id,
            "fields": "name,formatted_phone_number,website",
            "key": GOOGLE_API_KEY
        }

        response = requests.get(url, params=params)
        data = response.json()

        print("📍 PLACE DETAILS RESPONSE:", data)

        if data.get("status") == "OK":
            result = data.get("result", {})

            return {
                "phone": result.get("formatted_phone_number"),
                "website": result.get("website")
            }

        return {}

    except Exception as e:
        print("❌ Place Details Error:", str(e))
        return {}


def generate_leads(query: str, location: str) -> Dict:

    leads = []

    try:

        # --------------------------------------------------
        # GOOGLE PLACES
        # --------------------------------------------------

        print("🚀 Starting Google Places")

        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"

        params = {
            "query": f"{query} in {location}",
            "key": GOOGLE_API_KEY
        }

        response = requests.get(url, params=params)

        print("✅ Google Status:", response.status_code)

        data = response.json()

        if data.get("status") == "OK":

            results = data.get("results", [])

            for place in results[:20]:

                place_id = place.get("place_id")

                print("📍 Fetching details for:", place.get("name"))

                details = get_place_details(place_id) if place_id else {}

                leads.append({
                    "name": place.get("name"),
                    "address": place.get("formatted_address"),
                    "rating": place.get("rating"),
                    "user_ratings_total": place.get("user_ratings_total"),
                    "phone": details.get("phone"),
                    "website": details.get("website"),
                    "source": "google_places"
                })

        else:

            print("⚠️ Google Places unavailable:", data.get("status"))

    except Exception as e:

        print("❌ Google Places Exception:", str(e))

    # --------------------------------------------------
    # GUMTREE
    # --------------------------------------------------

    print("🚀 Starting Gumtree")

    try:

        gumtree_results = search_gumtree(
            location=location,
            max_items=20
        )

        print("✅ Gumtree Results:", gumtree_results.get("count"))

        leads.extend(gumtree_results.get("leads", []))

    except Exception as e:

        print("❌ Gumtree Error:", str(e))


    # --------------------------------------------------
    # FACEBOOK MARKETPLACE
    # --------------------------------------------------

    print("🚀 Starting Facebook Marketplace")

    try:

        marketplace_results = get_facebook_marketplace(
            location=location,
            max_items=20
        )

        print("✅ Facebook Results:", len(marketplace_results))

        leads.extend(marketplace_results)

    except Exception as e:

        print("❌ Facebook Marketplace Error:", str(e))
    # --------------------------------------------------
    # FILTER
    # --------------------------------------------------

    try:

        leads = filter_leads(leads)

    except Exception as e:

        print("⚠️ Filter Error:", str(e))

    print("✅ Returning", len(leads), "total leads")

    return {
        "success": True,
        "engine": "multi_source",
        "count": len(leads),
        "sources": [
            "google_places",
            "gumtree",
            "facebook_marketplace"
        ],
        "leads": leads
    }