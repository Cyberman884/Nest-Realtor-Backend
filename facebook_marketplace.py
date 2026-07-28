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

        run = client.actor(ACTOR_ID).call(run_input=run_input)

        print("RUN TYPE:", type(run))
        print("RUN:", run)

        dataset = client.dataset(run.default_dataset_id)

        # DEBUG
        items = list(dataset.iterate_items())

        print("Facebook items:", len(items))

        for item in items[:2]:
            print(item)

        leads = []

        for item in items:

            lead = {
                "title": item.get("marketplace_listing_title"),
                "price": item.get("listing_price.formatted_amount"),
                "url": item.get("listingUrl"),
                "facebook_url": item.get("facebookUrl"),
                "image": item.get("primary_listing_photo.photo_image_url"),
                "source": "facebook_marketplace"
            }

            leads.append(lead)

        print(f"✅ Facebook returned {len(leads)} listings")

        return leads

    except Exception as e:

        print("❌ Facebook Marketplace Error:", str(e))

        return []