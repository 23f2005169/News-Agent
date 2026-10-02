#!/usr/bin/env python3
"""
seed_kg_nodes.py

One-time seed script: embeds the course's week/project structure using the
same model as the rest of the pipeline (bge-small-en-v1.5), then inserts
the nodes and their precedes-edges into Supabase's kg_nodes / kg_edges
tables. Safe to re-run — uses upsert on id, so re-running updates rather
than duplicates.

Usage:
    python scripts/seed_kg_nodes.py
"""

import os
import sys

from sentence_transformers import SentenceTransformer

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from supabase import create_client

NODES = [
    ("week_0", "Bridge Course",
     "Linux shell, Git, Python environment setup, command-line basics for beginners"),
    ("week_1", "Dev Environment & Tooling",
     "VS Code, uv, development environment configuration, developer tooling"),
    ("week_2", "Deployment & API Engineering",
     "FastAPI, REST APIs, Docker, deploying applications"),
    ("week_3", "LLM Engineering",
     "Prompting, LLM APIs, working with large language models programmatically"),
    ("week_4", "RAG & Hybrid RAG",
     "Retrieval augmented generation, vector search, hybrid retrieval techniques"),
    ("week_5", "Agentic AI",
     "AI agents, tool use, multi-step autonomous LLM workflows"),
    ("week_6", "Web Data Acquisition & OSINT",
     "Web scraping, data collection, open-source intelligence techniques"),
    ("week_7", "CI/CD, Security & Cloud",
     "Continuous integration, deployment pipelines, cloud security basics"),
    ("week_8", "MLOps & Fine-Tuning",
     "Model fine-tuning, ML operations, production ML workflows"),
]

EDGES = [
    ("week_0", "week_1", "precedes"),
    ("week_1", "week_2", "precedes"),
    ("week_2", "week_3", "precedes"),
    ("week_3", "week_4", "precedes"),
    ("week_4", "week_5", "precedes"),
    ("week_5", "week_6", "precedes"),
    ("week_6", "week_7", "precedes"),
    ("week_7", "week_8", "precedes"),
]


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        sys.exit("[ERROR] Set SUPABASE_URL and SUPABASE_SERVICE_KEY (env or .env file).")

    print("[INFO] Loading embedding model: BAAI/bge-small-en-v1.5")
    model = SentenceTransformer("BAAI/bge-small-en-v1.5")

    supabase = create_client(url, key)

    print(f"[INFO] Embedding {len(NODES)} nodes...")
    descriptions = [desc for _, _, desc in NODES]
    vectors = model.encode(descriptions, show_progress_bar=True)

    node_rows = []
    for (node_id, name, desc), vector in zip(NODES, vectors):
        node_rows.append({
            "id": node_id,
            "name": name,
            "description": desc,
            "embedding": vector.tolist(),
        })

    print("[INFO] Upserting nodes...")
    supabase.table("kg_nodes").upsert(node_rows, on_conflict="id").execute()

    print(f"[INFO] Upserting {len(EDGES)} edges...")
    edge_rows = [
        {"from_node": a, "to_node": b, "relation": rel}
        for a, b, rel in EDGES
    ]
    supabase.table("kg_edges").upsert(edge_rows, on_conflict="from_node,to_node").execute()

    print(f"[DONE] Seeded {len(node_rows)} nodes and {len(edge_rows)} edges.")


if __name__ == "__main__":
    main()
