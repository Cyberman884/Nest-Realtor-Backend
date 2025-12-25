from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .url_builder import build_search_url

router = APIRouter(prefix="/ai", tags=["AI Leads"])


class LeadQuery(BaseModel):
    query: str
    country: str | None = "ZA"


@router.post("/leads")
async def resolve_leads(payload: LeadQuery):
    """
    Resolves an AI lead query into a search URL.
    (Baseline working version)
    """
    if not payload.query:
        raise HTTPException(status_code=400, detail="Query is required")

    url = build_search_url(
        query=payload.query,
        country=payload.country or "ZA"
    )

    return {
        "status": "ok",
        "query": payload.query,
        "country": payload.country,
        "search_url": url
    }
    
