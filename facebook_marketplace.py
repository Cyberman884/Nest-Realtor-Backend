import os
from apify_client import ApifyClient

APIFY_TOKEN = os.getenv("APIFY_TOKEN")

ACTOR_ID = "blackfalcondata/facebook-marketplace-scraper"

client = ApifyClient(APIFY_TOKEN) if APIFY_TOKEN else None

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
    """Accept clearly titled property listings; reject known prices below R250,000."""
    title = str(
        item.get("title")
        or item.get("name")
        or item.get("marketplace_listing_title")
        or ""
    ).strip().lower()

    if not title:
        return False

    non_property_terms = (
        "machine", "slimming", "cryolipolysis", "ems machine",
        "fat freezing", "weight loss", "phone", "laptop", "furniture",
        "sofa", "clothing", "watch", "camera", "motorcycle", "motorbike",
        "car for", "vehicle", "parts", "spares", "appliance", "service",
        "job vacancy", "for rent furniture",
    )
    if any(term in title for term in non_property_terms):
        return False

    property_terms = (
        "house", "houses", "home for sale", "property for sale",
        "real estate for sale", "residential property", "flat", "apartment",
        "townhouse", "duplex", "vacant land", "land for sale", "plot",
        "farm", "bedroom", "bedrooms", "stand for sale", "residential stand",
    )
    if not any(term in title for term in property_terms):
        return False

    price_value = (
        item.get("price")
        or item.get("priceRaw")
        or item.get("currentPrice")
        or item.get("listingPrice")
        or item.get("formattedPrice")
        or item.get("listing_price")
    )
    price = _price_as_rand(price_value)
    # Facebook sometimes omits price in the dataset even when the actor UI shows it.
    # Keep clearly titled property listings if price is missing; reject only a known low price.
    if price is not None and price < 250000:
        return False

    return True

def get_value(item, *paths):
    """Read a field, including nested fields."""
    for path in paths:
        value = item

        for key in path.split("."):
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)

        if value is not None and value != "":
            return value

    return None


def extract_location(item):
    """Extract Facebook's location from common flat and nested output fields."""
    location = get_value(
        item,
        "locationText",
        "location.text",
        "location.name",
        "location.city",
        "location.town",
        "location.address",
        "location.formatted_address",
        "locationName",
        "location_name",
        "listing_location",
        "item_location",
        "marketplace_listing_location.name",
        "marketplace_listing_location.city",
        "marketplace_listing_location.address",
        "marketplace_listing_location.location_text",
        "address",
        "city",
        "suburb",
        "town",
        "locality",
        "region",
        "state",
    )

    if isinstance(location, dict):
        location = (
            location.get("name")
            or location.get("city")
            or location.get("town")
            or location.get("address")
            or location.get("formatted_address")
            or location.get("location_text")
            or location.get("text")
        )

    if isinstance(location, (list, tuple)):
        location = ", ".join(str(part) for part in location if part)

    if location:
        return str(location).strip()

    # Some actor outputs place the location under a listing or seller object.
    fallback = get_value(
        item,
        "marketplace_listing_location",
        "seller_location",
        "sellerLocation",
    )
    if isinstance(fallback, dict):
        fallback = (
            fallback.get("name")
            or fallback.get("city")
            or fallback.get("town")
            or fallback.get("address")
            or fallback.get("formatted_address")
            or fallback.get("location_text")
        )
    if fallback:
        return str(fallback).strip()

    city = get_value(item, "city")
    state = get_value(item, "state")
    if city and state:
        return f"{city}, {state}"
    return city or state

def get_facebook_marketplace(
    location,
    max_items=20,
    query="houses for sale"
):
    try:
        if not client:
            raise ValueError("APIFY_TOKEN is missing")

        if not ACTOR_ID:
            raise ValueError("FACEBOOK_ACTOR_ID is missing")

        location = str(location or "").strip()

        if not location:
            raise ValueError("Location is required")

        run_input = {
            "availableOnly": True,
            "browseWithoutQuery": False,
            "compact": False,
            "deliveryMethod": "any",
            "descriptionFormat": "all",
            "emitUnchanged": False,
            "excludeEmptyFields": False,
            "includeDetails": True,
            "incrementalMode": False,
            "location": location,
            "maxResults": max_items,
            "notifyOnlyChanges": False,
            "query": str(query or "houses for sale").strip(),
            "radiusKm": 20,
            "sortBy": "relevance",
            "strictQueryMatch": False,
            "strictRadius": False,
            "startUrls": [],
            "conditions": [],
            "categories": [],
            "descriptionMaxLength": 0,
            "notificationLimit": 5,
        }

        print("Starting Black Falcon Facebook")
        print("Facebook query:", run_input["query"])
        print("Facebook location:", location)

        run = client.actor(ACTOR_ID).call(
            run_input=run_input
        )

        dataset_id = run.default_dataset_id

        dataset = client.dataset(
            dataset_id
        )

        leads = []

        for item in dataset.iterate_items():
            if not _is_property_listing(item):
                print(
                    "Filtered Facebook non-property/low-price listing:",
                    item.get("title") or item.get("marketplace_listing_title") or item.get("name"),
                )
                continue

            title = get_value(
                item,
                "title",
                "marketplace_listing_title",
                "name"
            )

            url = get_value(
                item,
                "listingUrl",
                "facebookUrl",
                "url",
                "listing_url",
                "itemUrl"
            )

            price = get_value(
                item,
                "price.formatted",
                "price.formattedAmount",
                "price.formatted_amount",
                "listing_price.formatted_amount",
                "price",
                "formattedPrice"
            )

            if isinstance(price, dict):
                price = (
                    price.get("formatted")
                    or price.get("formattedAmount")
                    or price.get("amount")
                    or price.get("value")
                )

            extracted_location = extract_location(item)
            if not extracted_location:
                print(
                    "Facebook location missing; available location keys:",
                    {
                        key: item.get(key)
                        for key in (
                            "location", "locationText", "locationName",
                            "location_name", "marketplace_listing_location",
                            "seller_location", "city", "town", "suburb", "address",
                        )
                        if item.get(key) not in (None, "", {}, [])
                    },
                )

            lead = {
                "title": title or "Property for sale",
                "price": price,
                "url": url,
                "facebook_url": get_value(
                    item, "facebookUrl", "url", "listingUrl"
                ),
                "image": get_value(
                    item,
                    "primaryPhotoUrl",
                    "primary_listing_photo.photo_image_url",
                    "image",
                    "imageUrl"
                ),
                "location": extracted_location,
                "description": get_value(
                    item,
                    "description",
                    "redacted_description",
                    "details"
                ),
                "source": "facebook_marketplace",
            }

            leads.append(lead)

        print(
            "Facebook listings returned:",
            len(leads)
        )

        print(
            "Facebook listings with location:",
            sum(1 for lead in leads if lead["location"]),
            "/",
            len(leads)
        )

        return leads

    except Exception as e:
        print("Facebook Marketplace error:", str(e))
        return []
