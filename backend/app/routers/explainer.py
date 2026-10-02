"""Explanation and traceability API endpoints."""
from __future__ import annotations

"""
backend/app/routers/explainer.py

GET /explainer/{item_id}

Replaces the earlier node_id/graph_driver scaffold — that version
belonged to the original Neo4j-based design. This version matches the
current plan: per-article caching, context gathered via
match_items_by_source instead of graph traversal.
"""

"""
backend/app/routers/explainer.py

GET /explainer/{item_id}
"""

from fastapi import APIRouter, HTTPException

from app.services.supabase_client import get_supabase_client
from app.services.llm import call_llm
from app.services.explainer_prompt import EXPLAINER_SYSTEM_PROMPT, build_explainer_prompt

router = APIRouter()

# Created once at import time and reused across requests, rather than
# calling get_supabase_client() fresh inside every route.
supabase = get_supabase_client()

FOUNDATION_SOURCE = "course_portal"
RELATED_SOURCES = ["arxiv", "article"]


@router.get("/{item_id}")
def get_explainer(item_id: str) -> dict[str, object]:
    if supabase is None:
        raise HTTPException(status_code=500, detail="Supabase is not configured (check SUPABASE_URL / SUPABASE_SERVICE_KEY).")

    # 1. Cache check
    cached = supabase.table("article_explainers").select("*").eq("item_id", item_id).execute()
    if cached.data:
        row = cached.data[0]
        return {
            "article": row["article_text"],
            "prerequisites": row.get("prerequisites") or [],
            "related": row.get("related") or [],
            "cached": True,
        }

    # 2. Fetch the target item
    target_res = supabase.table("items").select("*").eq("id", item_id).single().execute()
    if not target_res.data:
        raise HTTPException(status_code=404, detail="Item not found")
    target = target_res.data

    if not target.get("embedding"):
        raise HTTPException(status_code=400, detail="Item has no embedding yet")

    # 3. Gather context
    foundation_res = supabase.rpc("match_items_by_source", {
        "query_embedding": target["embedding"],
        "source_filter": FOUNDATION_SOURCE,
        "match_count": 3,
        "exclude_id": item_id,
    }).execute()
    foundation = foundation_res.data or []

    related: list[dict] = []
    for src in RELATED_SOURCES:
        res = supabase.rpc("match_items_by_source", {
            "query_embedding": target["embedding"],
            "source_filter": src,
            "match_count": 3,
            "exclude_id": item_id,
        }).execute()
        related.extend(res.data or [])
    related = related[:3]

    # 4. Generate
    user_prompt = build_explainer_prompt(target, foundation, related)
    try:
        article_text = call_llm(
            system_prompt=EXPLAINER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_output_tokens=1024,
            temperature=0.4,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {e}")

    # 5. Cache
    supabase.table("article_explainers").upsert({
        "item_id": item_id,
        "article_text": article_text,
        "prerequisites": foundation,
        "related": related,
    }).execute()

    return {
        "article": article_text,
        "prerequisites": foundation,
        "related": related,
        "cached": False,
    }