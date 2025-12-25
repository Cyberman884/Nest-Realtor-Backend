from urllib.parse import quote_plus


def build_search_url(query: str, country: str = "ZA") -> str:
    """
    Builds a Google-style search URL for real estate lead discovery.
    """
    base = "https://www.google.com/search?q="
    full_query = f"{query} site:property site:realestate site:estate"
    return base + quote_plus(full_query)
