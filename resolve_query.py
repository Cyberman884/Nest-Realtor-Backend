from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai.openai_client import resolve_query
from ai.url_builder import build_urls

router = APIRouter()

class ResolveRequest(BaseModel):
    prompt: str

@router.post("/ai/resolve-query")
def resolve_ai_query(body: ResolveRequest):
    try:
        resolved = resolve_query(body.prompt)
        urls = build_urls(resolved)

        return {
            "success": True,
            "resolved": resolved,
            "urls": urls
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
