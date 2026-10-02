"""Search API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.embeddings import embed_text
from app.services.supabase_client import get_supabase_client


router = APIRouter()


@router.get("")
def search(query: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=100)):
    """Return semantic matches for a user query."""
    supabase = get_supabase_client()
    if supabase is None:
        return {
            "query": query,
            "limit": limit,
            "results": [],
            "message": "Supabase is not configured yet.",
        }

    query_vector = embed_text(query)
    result = supabase.rpc(
        "match_items",
        {
            "query_embedding": query_vector,
            "match_count": limit,
            "exclude_id": None,
        },
    ).execute()
    return {"query": query, "limit": limit, "results": result.data}