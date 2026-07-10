from facebook_posts import fetch_facebook_posts
from facebook_marketplace import fetch_marketplace
from gumtree import fetch_gumtree


def collect_opportunities(search_query, max_results=20):
    opportunities = []

    try:
        opportunities.extend(fetch_facebook_posts(search_query, max_results))
    except Exception as e:
        print(f"Facebook Posts Error: {e}")

    try:
        opportunities.extend(fetch_marketplace(search_query, max_results))
    except Exception as e:
        print(f"Marketplace Error: {e}")

    try:
        opportunities.extend(fetch_gumtree(search_query, max_results))
    except Exception as e:
        print(f"Gumtree Error: {e}")

    return opportunities