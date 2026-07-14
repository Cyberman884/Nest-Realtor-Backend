from apify_client import ApifyClient
import os

APIFY_TOKEN = os.getenv("APIFY_TOKEN")

client = ApifyClient(APIFY_TOKEN)

ACTOR_ID = "JziY9YnglkuoWMDsq"


def build_gumtree_url(location: str):
    """
    Build Gumtree URL dynamically.
    """

    location = location.strip().lower()

    # Nationwide search
    if location in ["south africa", "sa", "rsa", "all"]:
        return "https://www.gumtree.co.za/s-houses-flats-for-sale/v1c9074p1"

    # Convert city names to Gumtree slug
    slug = (
        location.replace(" ", "-")
                .replace("_", "-")
    )

    return (
        f"https://www.gumtree.co.za/"
        f"s-houses-flats-for-sale/{slug}/"
    )


def search_gumtree(location: str, max_items: int = 20):

    search_url = build_gumtree_url(location)

    print("🚀 Starting Gumtree")
    print("Search URL:", search_url)

    run_input = {
        "startUrls": [
            {
                "url": search_url
            }
        ],
        "maxItems": max_items,
        "includeListingDetails": True,
        "cookies": [],
        "proxy": {
            "useApifyProxy": True
        }
    }

    try:

        run = client.actor(ACTOR_ID).call(run_input=run_input)

        dataset = client.dataset(run["defaultDatasetId"])

        leads = []

        for item in dataset.iterate_items():

            seller_type = (
                item.get("sellerType")
                or item.get("seller_type")
                or ""
            )

            seller_type = str(seller_type).lower()

            if seller_type not in [
                "private",
                "owner",
                "private seller"
            ]:
                continue

            lead = {
                "title": item.get("title"),
                "price": item.get("price"),
                "currency": item.get("currency"),
                "location": item.get("location"),
                "category": item.get("category"),
                "seller_type": seller_type,
                "posted_date": item.get("postedDate"),
                "url": item.get("link"),
                "source": "gumtree"
            }

            leads.append(lead)

        print(f"✅ Gumtree returned {len(leads)} leads")

        return {
            "success": True,
            "engine": "gumtree",
            "count": len(leads),
            "leads": leads
        }

    except Exception as e:

        print("❌ Gumtree Error:", str(e))

        return {
            "success": False,
            "engine": "gumtree",
            "count": 0,
            "leads": [],
            "error": str(e)
        }