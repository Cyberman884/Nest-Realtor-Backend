from apify_client import ApifyClient
import os

APIFY_TOKEN = os.getenv("APIFY_TOKEN")

client = ApifyClient(APIFY_TOKEN)

ACTOR_ID = "JziY9YnglkuoWMDsq"


def build_gumtree_url(location: str):

    location = location.strip().lower()

    cities = {
        "johannesburg": "johannesburg",
        "pretoria": "pretoria-tshwane",
        "cape town": "cape-town",
        "durban": "durban-city",
        "east london": "east-london",
        "port elizabeth": "port-elizabeth",
        "gqeberha": "port-elizabeth",
        "bloemfontein": "bloemfontein",
        "polokwane": "polokwane-pietersburg",
        "nelspruit": "nelspruit",
        "mbombela": "nelspruit",
        "kimberley": "kimberley"
    }

    if location in ["south africa", "sa", "rsa", "all", ""]:
        return "https://www.gumtree.co.za/s-houses-flats-for-sale/v1c9074p1"

    slug = cities.get(location)

    if slug:
        return f"https://www.gumtree.co.za/s-houses-flats-for-sale/{slug}/v1c9074p1"

    slug = location.replace(" ", "-")

    return f"https://www.gumtree.co.za/s-houses-flats-for-sale/{slug}/v1c9074p1"


def search_gumtree(location, max_items=20):

    url = build_gumtree_url(location)

    print("🚀 Starting Gumtree")
    print("URL:", url)

    run_input = {
        "startUrls": [
            {
                "url": url
            }
        ],
        "maxItems": max_items,
        "includeListingDetails": True
    }

    try:

        run = client.actor(ACTOR_ID).call(run_input=run_input)

        dataset = client.dataset(run["defaultDatasetId"])

        leads = []

        for item in dataset.iterate_items():

            lead = {
                "title": item.get("title"),
                "price": item.get("price"),
                "currency": item.get("currency"),
                "location": item.get("location"),
                "category": item.get("category"),
                "seller_type": item.get("sellerType"),
                "posted_date": item.get("postedDate"),
                "url": item.get("link"),
                "source": "gumtree"
            }

            leads.append(lead)

        print(f"✅ Gumtree returned {len(leads)} listings")

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