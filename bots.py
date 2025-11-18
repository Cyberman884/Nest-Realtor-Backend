# bots.py
# Centralized lead generation bot functions for Nest Realtor
# NOTE: Replace API key env vars in your hosting environment

import os
import requests
from bs4 import BeautifulSoup

SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
BRIGHTDATA_KEY = os.getenv("BRIGHTDATA_KEY")

# -------------------------------------------------------------
# 🔍 REAL ESTATE BUYER LEAD SCRAPER
# -------------------------------------------------------------

def search_buyer_leads(location: str, min_price: int = 0, max_price: int = 999999999):
    """
    Scrapes public property listing search results using ScraperAPI.
    """
    try:
        url = (
            f"https://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url="
            f"https://www.property24.com/for-sale/{location}/1"
        )

        r = requests.get(url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        results = []
        listings = soup.select(".p24_regularTile")

        for item in listings:
            title = item.select_one(".p24_title").get_text(strip=True) if item.select_one(".p24_title") else ""
            price = item.select_one(".p24_price").get_text(strip=True) if item.select_one(".p24_price") else ""
            link = "https://www.property24.com" + item.find("a").get("href") if item.find("a") else None

            results.append({"title": title, "price": price, "link": link})

        return {"status": "success", "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# -------------------------------------------------------------
# 🏡 SELLER LEAD SCRAPER
# -------------------------------------------------------------

def search_seller_leads(location: str):
    """
    Scrapes FSBO (For Sale By Owner) type listings.
    """
    try:
        url = (
            f"https://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url="
            f"https://www.gumtree.co.za/s-houses-flats-for-sale/{location}/v1c9074l3100001p1"
        )

        r = requests.get(url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        results = []
        listings = soup.select(".related-ad-title")

        for item in listings:
            title = item.get_text(strip=True)
            link = "https://www.gumtree.co.za" + item.get("href")

            results.append({"title": title, "link": link})

        return {"status": "success", "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# -------------------------------------------------------------
# 🌐 SOCIAL MEDIA LEADS (SERP API)
# -------------------------------------------------------------

def social_media_leads(keyword: str, platform: str = "instagram"):
    """
    Grabs social media pages using SERP API.
    """
    try:
        url = (
            f"https://serpapi.com/search.json?engine=google&q={keyword}+{platform}+real+estate"
            f"&api_key={SERPAPI_KEY}"
        )

        r = requests.get(url, timeout=20).json()
        results = []

        if "organic_results" in r:
            for item in r["organic_results"]:
                results.append(
                    {
                        "title": item.get("title"),
                        "link": item.get("link"),
                        "snippet": item.get("snippet"),
                    }
                )

        return {"status": "success", "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# -------------------------------------------------------------
# 🌍 UNIVERSAL LEAD SEARCH (BRIGHTDATA / ScraperAPI)
# -------------------------------------------------------------

def universal_lead_scraper(url: str):
    """
    Scrapes ANY website URL using ScraperAPI.
    """
    try:
        api_url = f"https://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={url}"
        r = requests.get(api_url, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")

        title = soup.title.get_text(strip=True) if soup.title else "No Title"
        text = soup.get_text(" ", strip=True)[:2000]  # summary

        return {
            "status": "success",
            "source_url": url,
            "page_title": title,
            "preview_text": text,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
