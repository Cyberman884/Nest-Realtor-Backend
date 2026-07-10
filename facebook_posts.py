import os
import requests

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
ACTOR_ID = "YOUR_FACEBOOK_POSTS_ACTOR_ID"


def fetch_facebook_posts(search_query, max_results=20):
    """
    Runs the Facebook Posts actor and returns the dataset.
    """

    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={APIFY_TOKEN}"

    actor_input = {
        "searchQuery": search_query,
        "maxResults": max_results
    }

    response = requests.post(url, json=actor_input)

    response.raise_for_status()

    run = response.json()["data"]

    dataset_id = run["defaultDatasetId"]

    dataset_url = (
        f"https://api.apify.com/v2/datasets/"
        f"{dataset_id}/items?token={APIFY_TOKEN}"
    )

    dataset = requests.get(dataset_url)

    dataset.raise_for_status()

    return dataset.json()