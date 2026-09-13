from apify_client import ApifyClient
import os


APIFY_TOKEN = os.getenv("APIFY_TOKEN")

client = ApifyClient(APIFY_TOKEN)

ACTOR_ID = "U5DUNxhH3qKt5PnCf"


def build_marketplace_url(location):

    location = location.lower().strip()

    if location in ["south africa", "sa", "rsa", "all", ""]:
        return "https://www.facebook.com/marketplace/southafrica/propertyforsale"

    slug = location.replace(" ", "")

    return f"https://www.facebook.com/marketplace/{slug}/propertyforsale"


def extract_location(item):

    # Try the most common location fields returned by Marketplace data
    candidates = [
        item.get("location"),
        item.get("location_name"),
        item.get("listing_location"),
        item.get("marketplace_listing_location"),
        item.get("address"),
        item.get("city"),
        item.get("town"),
        item.get("suburb"),
        item.get("locality"),
        item.get("region"),
    ]

    for value in candidates:

        if isinstance(value, dict):

            value = (
                value.get("name")
                or value.get("city")
                or value.get("town")
                or value.get("address")
                or value.get("formatted_address")
            )

        if value:
            return str(value)

    return None


def get_facebook_marketplace(location, max_items=20):

    try:

        url = build_marketplace_url(location)

        print("🚀 Starting Facebook Marketplace")
        print("URL:", url)

        run_input = {
            "startUrls": [
                {
                    "url": url
                }
            ],
            "resultsLimit": max_items,
            "includeListingDetails": False
        }

        run = client.actor(ACTOR_ID).call(
            run_input=run_input
        )

        print("RUN TYPE:", type(run))
        print("RUN:", run)

        dataset = client.dataset(
            run.default_dataset_id
        )

        leads = []

        for item in dataset.iterate_items():

            listing_location = extract_location(item)

            lead = {
                "title": item.get(
                    "marketplace_listing_title"
                ),

                "price": item.get(
                    "listing_price.formatted_amount"
                ),

                "url": item.get(
                    "listingUrl"
                ),

                "facebook_url": item.get(
                    "facebookUrl"
                ),

                "image": item.get(
                    "primary_listing_photo.photo_image_url"
                ),

                "location": listing_location,

                "source": "facebook_marketplace"
            }

            leads.append(lead)

        print(
            f"✅ Facebook returned {len(leads)} listings"
        )

        # Helpful diagnostic
        locations_found = sum(
            1 for lead in leads
            if lead.get("location")
        )

        print(
            f"📍 Facebook listings with location: "
            f"{locations_found}/{len(leads)}"
        )

        return leads

    except Exception as e:

        print(
            "❌ Facebook Marketplace Error:",
            str(e)
        )

        return []