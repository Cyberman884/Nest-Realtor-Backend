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

    try:

        print("🚀 Starting Google Places")

        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"

        params = {
            "query": f"{query} in {location}",
            "key": GOOGLE_API_KEY
        }

        response = requests.get(url, params=params)

        print("✅ Google Status:", response.status_code)

        data = response.json()

        if data.get("status") != "OK":
            raise Exception(f"Google API Error: {data.get('status')}")

        results = data.get("results", [])

        leads = []

        for place in results[:20]:

            place_id = place.get("place_id")

            print("📍 Fetching details for:", place.get("name"))

            details = get_place_details(place_id) if place_id else {}

            lead = {
                "name": place.get("name"),
                "address": place.get("formatted_address"),
                "rating": place.get("rating"),
                "user_ratings_total": place.get("user_ratings_total"),
                "phone": details.get("phone"),
                "website": details.get("website"),
                "source": "google_places"
            }

            leads.append(lead)

        # -------------------------------
        # GUMTREE
        # -------------------------------

        print("🚀 Starting Gumtree")

        gumtree_url = GUMTREE_URLS.get(location.lower())

        print("Gumtree URL:", gumtree_url)

        try:

            if gumtree_url:

                gumtree_results = search_gumtree(
                    gumtree_url,
                    max_items=20
                )

                print("✅ Gumtree Results:", gumtree_results.get("count"))

                leads.extend(gumtree_results.get("leads", []))

            else:

                print("⚠️ No Gumtree URL found for", location)

        except Exception as e:

            print("❌ Gumtree Error:", str(e))

        # -------------------------------
        # FACEBOOK MARKETPLACE
        # -------------------------------

        print("🚀 Starting Facebook Marketplace")

        marketplace_url = FACEBOOK_MARKETPLACE_URLS.get(location.lower())

        print("Marketplace URL:", marketplace_url)

        try:

            if marketplace_url:

                marketplace_results = get_facebook_marketplace(
                    marketplace_url,
                    max_items=20
                )

                print("✅ Facebook Results:", len(marketplace_results))

                leads.extend(marketplace_results)

            else:

                print("⚠️ No Facebook Marketplace URL found for", location)

        except Exception as e:

            print("❌ Facebook Marketplace Error:", str(e))

        # -------------------------------
        # FILTER
        # -------------------------------

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

    except Exception as e:

        print("❌ GOOGLE ERROR:", str(e))

        return {
            "success": False,
            "engine": "fallback",
            "leads": [],
            "error": str(e)
        }