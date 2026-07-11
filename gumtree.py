from apify_client import ApifyClient
import os

APIFY_TOKEN = os.getenv("APIFY_TOKEN")

client = ApifyClient(APIFY_TOKEN)


def search_gumtree(url: str, max_items: int = 10):
    """
    Search Gumtree South Africa for private property sellers.
    """

    run_input = {
        "startUrls": [
            {
                "url": url
            }
        ],
        "maxItems": max_items,
        "includeListingDetails": True,
        "cookies": [],
        "proxy": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"]
        }
    }

    try:

        run = client.actor("JziY9YnglkuoWMDsq").call(run_input=run_input)

        dataset = client.dataset(run.default_dataset_id)

        leads = []

        for item in dataset.iterate_items():

            seller_type = (
                item.get("sellerType")
                or item.get("seller_type")
                or ""
            )

            if str(seller_type).lower() not in [
                "private",
                "owner",
                "private seller"
            ]:
                continue

            leads.append({
                "title": item.get("title"),
                "price": item.get("price"),
                "currency": item.get("currency"),
                "location": item.get("location"),
                "category": item.get("category"),
                "seller_type": seller_type,
                "posted_date": item.get("postedDate"),
                "url": item.get("link"),
                "source": "gumtree"
            })

        return {
            "success": True,
            "engine": "gumtree",
            "count": len(leads),
            "leads": leads
        }

    except Exception as e:

        print("GUMTREE ERROR:", str(e))

        return {
            "success": False,
            "engine": "gumtree",
            "count": 0,
            "leads": [],
            "error": str(e)
        }