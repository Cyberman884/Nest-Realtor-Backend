import os
from apify_client import ApifyClient

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
ACTOR_ID = "solidcode/gumtree-scraper"
client = ApifyClient(APIFY_TOKEN)


def _value(item, *keys):
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def search_gumtree(location, max_items=5):
    """Thin Nest -> SolidCode Gumtree integration.

    Uses the same successful search pattern observed in the direct
    SolidCode run: 'Houses for sale in <location>'.
    No coordinate or location validation is performed here.
    """
    location = str(location or "").strip()

    if not location:
        return {"success": False, "engine": "gumtree", "count": 0,
                "leads": [], "error": "Location is required"}

    if not APIFY_TOKEN:
        print("❌ APIFY_TOKEN is missing")
        return {"success": False, "engine": "gumtree", "count": 0,
                "leads": [], "error": "APIFY_TOKEN is not configured"}

    search_keyword = f"Houses for sale in {location}"
    run_input = {
        "category": "all",
        "includeListingDetails": True,
        "includePhone": False,
        "maxResults": int(max_items),
        "region": "za",
        "searchKeyword": search_keyword,
        "sortBy": "most_recent"
    }

    print("🚀 Starting SolidCode Gumtree")
    print("📍 Requested location:", location)
    print("🔎 Search keyword:", search_keyword)
    print("🔢 Max items:", max_items)
    print("🧾 SolidCode input:", run_input)

    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        dataset_id = getattr(run, "default_dataset_id", None)
        if not dataset_id and isinstance(run, dict):
            dataset_id = run.get("defaultDatasetId") or run.get("default_dataset_id")
        if not dataset_id:
            raise RuntimeError("SolidCode run did not return a dataset ID")

        print("📦 Dataset:", dataset_id)
        dataset = client.dataset(dataset_id)
        leads = []

        for item in dataset.iterate_items():
            location_value = _value(item, "location", "locationName", "location_name",
                                     "address", "suburb", "area", "city", "town")
            seller_name = _value(item, "sellerName", "seller_name", "seller")
            seller_type = _value(item, "sellerType", "seller_type")
            images = item.get("images")
            image = images[0] if isinstance(images, list) and images else _value(
                item, "image", "imageUrl", "image_url"
            )

            lead = {
                "title": _value(item, "title", "name"),
                "price": _value(item, "price", "currentPrice", "listingPrice", "priceRaw"),
                "price_raw": item.get("priceRaw"),
                "previous_price": _value(item, "previousPrice", "previous_price", "oldPrice", "originalPrice"),
                "currency": _value(item, "currency"),
                "location": location_value,
                "address": _value(item, "address", "formattedAddress") or location_value,
                "suburb": _value(item, "suburb", "area") or location_value,
                "city": _value(item, "city", "town"),
                "region": _value(item, "region"),
                "category": _value(item, "category", "propertyType", "property_type"),
                "property_type": _value(item, "propertyType", "property_type", "category"),
                "seller_type": seller_type,
                "seller": seller_name,
                "seller_name": seller_name,
                "description": _value(item, "description", "details"),
                "posted_date": _value(item, "postedAt", "postedDate", "posted_date", "datePosted"),
                "days_on_market": _value(item, "daysOnSite", "daysOnMarket", "days_on_market", "daysListed", "days_listed"),
                "days_on_site": _value(item, "daysOnSite", "daysOnMarket", "days_on_market", "daysListed", "days_listed"),
                "url": _value(item, "url", "link", "listingUrl", "sourceUrl"),
                "image": image,
                "images": images if isinstance(images, list) else [],
                "image_count": _value(item, "imageCount"),
                "latitude": _value(item, "latitude", "lat"),
                "longitude": _value(item, "longitude", "lon", "lng"),
                "listing_id": _value(item, "listingId", "shortId"),
                "short_id": item.get("shortId"),
                "attributes": item.get("attributes") if isinstance(item.get("attributes"), dict) else {},
                "featured": item.get("featured"),
                "urgent": item.get("urgent"),
                "source": "gumtree"
            }
            leads.append(lead)
            print("🔎 SolidCode listing:", lead["title"])
            print("   Location:", lead["location"])
            print("   Price:", lead["price"])
            print("   Seller:", lead["seller"])

        print(f"✅ SolidCode Gumtree returned {len(leads)} listings")
        return {"success": True, "engine": "gumtree", "count": len(leads), "leads": leads}

    except Exception as e:
        print("❌ SolidCode Gumtree Error:", str(e))
        return {"success": False, "engine": "gumtree", "count": 0, "leads": [], "error": str(e)}
