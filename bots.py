# bots.py
# Centralized lead generation bot functions for Nest Realtor
# NOTE: Replace API key env vars in your hosting environment

import os
import requests
from bs4 import BeautifulSoup
import time
import urllib.parse

SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
BRIGHTDATA_KEY = os.getenv("BRIGHTDATA_KEY")

# -------------------------------------------------------------
# 🔍 REAL ESTATE BUYER LEAD SCRAPER (Property24 / ScraperAPI)
# -------------------------------------------------------------
def search_buyer_leads(location: str, limit: int = 20, min_price: int = 0, max_price: int = 999999999):
    try:
        if SCRAPERAPI_KEY:
            url = (
                f"https://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url="
                + urllib.parse.quote(f"https://www.property24.com/for-sale/{location}/1")
            )
        else:
            url = f"https://www.property24.com/for-sale/{location}/1"
        r = requests.get(url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        listings = soup.select(".p24_regularTile") or soup.select(".listing, .listing-item")
        for item in listings[:limit]:
            title = item.select_one(".p24_title").get_text(strip=True) if item.select_one(".p24_title") else (item.get_text(strip=True)[:120] if item else "")
            price = item.select_one(".p24_price").get_text(strip=True) if item.select_one(".p24_price") else ""
            a = item.find("a")
            link = ("https://www.property24.com" + a.get("href")) if a and a.get("href") and a.get("href").startswith("/") else (a.get("href") if a else None)
            results.append({"title": title, "price": price, "link": link, "source": "property24"})
        return {"status": "success", "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -------------------------------------------------------------
# 🏡 SELLER LEAD SCRAPER (Gumtree)
# -------------------------------------------------------------
def search_seller_leads(location: str, limit: int = 20):
    try:
        if SCRAPERAPI_KEY:
            url = f"https://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url=" + urllib.parse.quote(f"https://www.gumtree.co.za/s-houses-flats-for-sale/{location}/v1c9074l3100001p1")
        else:
            url = f"https://www.gumtree.co.za/s-houses-flats-for-sale/{location}/v1c9074l3100001p1"
        r = requests.get(url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        listings = soup.select(".related-ad-title") or soup.select(".listing-title, .user-ad-row")
        for item in listings[:limit]:
            title = item.get_text(strip=True)
            link = item.get("href") or (item.find("a").get("href") if item.find("a") else None)
            if link and link.startswith("/"):
                link = "https://www.gumtree.co.za" + link
            results.append({"title": title, "link": link, "source": "gumtree"})
        return {"status": "success", "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -------------------------------------------------------------
# 🌐 SOCIAL MEDIA LEADS (SERP API or Google fallback)
# -------------------------------------------------------------
def social_media_leads(query: str, platform: str = "instagram", limit: int = 20):
    """
    Use SerpApi if SERPAPI_KEY is present, otherwise fallback to Google search scraping.
    Returns: {status, count, results:[{title,link,snippet,platform}]}
    """
    try:
        results = []
        if SERPAPI_KEY:
            # SerpApi Google search for platform results
            q = f"{platform} {query} real estate"
            api = f"https://serpapi.com/search.json?engine=google&q={urllib.parse.quote(q)}&api_key={SERPAPI_KEY}"
            r = requests.get(api, timeout=15).json()
            for item in (r.get("organic_results") or [])[:limit]:
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet"),
                    "platform": platform
                })
            return {"status": "success", "count": len(results), "results": results}
        # fallback: simple Google HTML search scraping (public)
        q = f"{platform} {query} real estate"
        url = f"https://www.google.com/search?q={urllib.parse.quote(q)}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NestRealtorBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        # Google structure: div.g containers
        items = soup.select("div.g") or soup.select(".rc")
        for item in items[:limit]:
            a = item.find("a")
            title = item.get_text(strip=True)[:140]
            link = a.get("href") if a else None
            snippet = item.select_one(".IsZvec") and item.select_one(".IsZvec").get_text(strip=True) or ""
            results.append({"title": title, "link": link, "snippet": snippet, "platform": platform})
            # be polite
            time.sleep(0.1)
        return {"status": "success", "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -------------------------------------------------------------
# 🌍 UNIVERSAL LEAD SEARCH (BRIGHTDATA / ScraperAPI)
# -------------------------------------------------------------
def universal_lead_scraper(url: str):
    try:
        if SCRAPERAPI_KEY:
            api_url = f"https://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={urllib.parse.quote(url, safe='')}"
            r = requests.get(api_url, timeout=30)
        else:
            r = requests.get(url, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else "No Title"
        text = soup.get_text(" ", strip=True)[:2000]
        return {"status": "success", "source_url": url, "page_title": title, "preview_text": text}
    except Exception as e:
        return {"status": "error", "message": str(e)}
