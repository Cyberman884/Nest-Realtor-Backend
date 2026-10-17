import os
from apify_client import ApifyClient

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
ACTOR_ID = "solidcode/gumtree-scraper"
client = ApifyClient(APIFY_TOKEN)

def _price_as_rand(value):
    """Convert a listing price to a Rand amount."""
    if value is None:
        return None

    if isinstance(value, dict):
        value = (
            value.get("formatted")
            or value.get("formattedAmount")
            or value.get("formatted_amount")
            or value.get("amount")
            or value.get("value")
            or value.get("price")
        )
        if value is None:
            return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).upper().replace(",", "").replace("ZAR", "").replace("R", "").strip()
    multiplier = 1
    if "MILLION" in text or text.endswith("M"):
        multiplier = 1_000_000
    elif "THOUSAND" in text or text.endswith("K"):
        multiplier = 1_000

    digits = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    try:
        return float(digits) * multiplier if digits else None
    except (ValueError, TypeError):
        return None


def _is_property_listing(item):
    """Fail closed: only accept clearly titled property listings at R250,000+."""
    # Use the TITLE as the main evidence. Description-only matches are unsafe:
    # a non-property product can mention a house or property in its description.
    title = str(
        item.get("title")
        or item.get("name")
        or item.get("marketplace_listing_title")
        or ""
    ).strip().lower()

    if not title:
        return False

    # Reject obvious non-property products/services before checking property terms.
    non_property_terms = (
        "machine", "slimming", "cryolipolysis", "ems machine",
        "fat freezing", "weight loss", "phone", "laptop", "furniture",
        "sofa", "clothing", "watch", "camera", "motorcycle", "motorbike",
        "car for", "vehicle", "parts", "spares", "appliance", "service",
        "job vacancy", "for rent furniture",
    )
    if any(term in title for term in non_property_terms):
        return False

    # These terms must appear in the title itself; generic "for sale" alone
    # is deliberately not enough to qualify a listing as property.
    property_terms = (
        "house", "houses", "home for sale", "property for sale",
        "real estate for sale", "residential property", "flat", "apartment",
        "townhouse", "duplex", "vacant land", "land for sale", "plot",
        "farm", "bedroom", "bedrooms", "stand for sale", "residential stand",
    )
    if not any(term in title for term in property_terms):
        return False

    # Read common price fields, including nested/formatted actor output.
    price_value = (
        item.get("price")
        or item.get("priceRaw")
        or item.get("currentPrice")
        or item.get("listingPrice")
        or item.get("formattedPrice")
        or item.get("listing_price")
    )
    price = _price_as_rand(price_value)
    if price is None or price < 250000:
        return False

    return True

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
            if not _is_property_listing(item):
                print(
                    "Filtered Gumtree non-property/low-price listing:",
                    item.get("title") or item.get("name"),
                )
                continue

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
