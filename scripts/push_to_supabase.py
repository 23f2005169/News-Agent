#!/usr/bin/env python3
"""
push_to_supabase.py

Upserts an embedded JSONL file into a Supabase table. Source-agnostic:
works for course_portal, arxiv, or news records as long as they follow
the canonical schema.

Idempotent: uses upsert on "id", so re-running never creates duplicates,
and re-pushing a record after re-tagging/re-embedding updates it in place.

Env vars (from your shell or a .env file):
    SUPABASE_URL          e.g. https://xxxx.supabase.co
    SUPABASE_SERVICE_KEY  the service_role key (server-side scripts ONLY,
                          never put this in the frontend)

Usage:
    python push_to_supabase.py --input data/embedded/TDSembedded_data.jsonl
    python push_to_supabase.py --input arxiv_embedded.jsonl --table items --batch-size 50
    python push_to_supabase.py --input data/embedded/TDSembedded_data.jsonl --dry-run
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from supabase import create_client

# Only these keys are sent to the database. Anything else in the JSONL
# (scratch fields, future additions) is dropped so PostgREST doesn't
# reject the whole batch for an unknown column.
COLUMNS = [
    "id", "source_type", "title", "raw_text", "source_url", "published_date",
    "scraped_category", "word_count", "content_hash", "links", "scraped_at",
    "subfield_tag", "entities", "relates_to_topics", "summary", "embedding",
    "kg_node_id",
]


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] Skipping unparseable line {line_num}: {e}", file=sys.stderr)
    return records


def to_row(record: dict) -> dict:
    return {col: record.get(col) for col in COLUMNS}


def chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main():
    parser = argparse.ArgumentParser(description="Upsert an embedded JSONL file into Supabase.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--table", default="items")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true",
                         help="Validate and report what would be pushed, without writing anything.")
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"[ERROR] Input file not found: {args.input}")

    records = load_jsonl(args.input)
    print(f"[INFO] Loaded {len(records)} records from {args.input}")

    # Dedupe by id (a batch containing the same id twice makes Postgres reject the upsert)
    unique = {}
    for r in records:
        if not r.get("id"):
            print("[WARN] Skipping record with no id", file=sys.stderr)
            continue
        unique[str(r["id"])] = r
    rows = [to_row(r) for r in unique.values()]
    for row in rows:
        row["id"] = str(row["id"])

    if len(rows) != len(records):
        print(f"[INFO] {len(records) - len(rows)} records dropped (duplicate or missing id)")

    missing_embedding = sum(1 for r in rows if not r.get("embedding"))
    print(f"[INFO] {len(rows)} rows ready, {missing_embedding} without an embedding")

    if args.dry_run:
        print("[DRY RUN] Nothing written. Sample row (embedding truncated):")
        sample = dict(rows[0])
        if sample.get("embedding"):
            sample["embedding"] = sample["embedding"][:3] + ["..."]
        print(json.dumps(sample, indent=2, ensure_ascii=False)[:1500])
        return

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        sys.exit("[ERROR] Set SUPABASE_URL and SUPABASE_SERVICE_KEY (env or .env file).")

    client = create_client(url, key)

    pushed, failed = 0, 0
    batches = list(chunked(rows, args.batch_size))
    for n, batch in enumerate(batches, 1):
        ok = False
        for attempt in (1, 2):
            try:
                client.table(args.table).upsert(batch, on_conflict="id").execute()
                ok = True
                break
            except Exception as e:
                print(f"[WARN] Batch {n}/{len(batches)} attempt {attempt} failed: {e}")
                if attempt == 1:
                    time.sleep(2)
        if ok:
            pushed += len(batch)
        else:
            failed += len(batch)
        print(f"[PROGRESS] Batch {n}/{len(batches)} done ({pushed} pushed, {failed} failed)")

    print(f"[DONE] Pushed: {pushed} | Failed: {failed} | Table: {args.table}")


if __name__ == "__main__":
    main()
