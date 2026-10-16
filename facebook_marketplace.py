import os
from apify_client import ApifyClient

APIFY_TOKEN = os.getenv("APIFY_TOKEN")

ACTOR_ID = "blackfalcondata/facebook-marketplace-scraper"

client = ApifyClient(APIFY_TOKEN) if APIFY_TOKEN else None

def _price_as_rand(value):
    """Convert a listing price to a Rand amount."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).upper().replace(",", "").replace("R", "").replace("ZAR", "").strip()

    digits = "".join(ch for ch in text if ch.isdigit() or ch == ".")

    try:
        return float(digits) if digits else None
    except (ValueError, TypeError):
        return None


def _is_property_listing(item):
    """Reject obvious non-property listings and prices below R250,000."""
    title = str(item.get("title") or item.get("name") or "").lower()
    description = str(item.get("description") or "").lower()
    category = str(item.get("category") or item.get("propertyType") or "").lower()
    text = f"{title} {description} {category}"

    property_terms = (
        "house", "home", "property", "flat", "apartment",
        "townhouse", "duplex", "vacant land", "plot",
        "farm", "estate", "bedroom", "for sale"
    )

    non_property_terms = (
        "machine", "slimming", "cryolipolysis", "ems machine",
        "fat freezing", "weight loss", "phone", "laptop",
        "furniture", "sofa", "clothing", "watch", "camera",
        "motorcycle", "motorbike", "parts", "spares"
    )

    if any(term in text for term in non_property_terms):
        return False

    if not any(term in text for term in property_terms):
        return False

    price = _price_as_rand(
        item.get("price")
        or item.get("priceRaw")
        or item.get("currentPrice")
        or item.get("listingPrice")
    )

    if price is None or price < 250000:
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
    location = get_value(
        item,
        "locationText",
        "location",
        "location_name",
        "listing_location",
        "item_location",
        "address",
        "city",
        "suburb",
        "town",
        "locality",
        "region",
    )

    if isinstance(location, dict):
        location = (
            location.get("name")
            or location.get("city")
            or location.get("town")
            or location.get("address")
            or location.get("formatted_address")
        )

    if location:
        return str(location)

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
                "location": extract_location(item),
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
