from apify_client import ApifyClient
import os

APIFY_TOKEN = os.getenv("APIFY_TOKEN")

client = ApifyClient(APIFY_TOKEN)

ACTOR_ID = "U5DUNxhH3qKt5PnCf"


def get_facebook_marketplace(url, max_items=20):
    try:

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

        dataset = client.dataset(run.default_dataset_id)

        results = []

        for item in dataset.iterate_items():

            lead = {
                "title": item.get("title"),
                "price": item.get("price"),
                "location": item.get("location"),
                "seller": item.get("sellerName"),
                "url": item.get("url"),
                "image": item.get("image"),
                "source": "facebook_marketplace"
            }

            results.append(lead)

        return results

    except Exception as e:
        print("Facebook Marketplace Error:", str(e))
        return []