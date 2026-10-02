#!/usr/bin/env python3
"""
generate_embeddings.py

Adds embeddings to a tagged JSONL file, embedding the "summary" field
(short and clean, rather than raw_text) using a local sentence-transformers
model — no API calls, no cost, runs identically in dev and in a deployed
container.

Usage:
    python generate_embeddings.py --input data/tagged/TDStagged_data.jsonl --output data/embedded/TDSembedded_data.jsonl
    python generate_embeddings.py --input arxiv_tagged.jsonl --output arxiv_embedded.jsonl --model-name BAAI/bge-small-en-v1.5
"""

import argparse
import json
import sys
import time
from pathlib import Path

from sentence_transformers import SentenceTransformer


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


def save_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Add embeddings to a tagged JSONL file.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--text-field", default="summary",
                         help="Which field to embed (default: summary).")
    parser.add_argument("--model-name", default="BAAI/bge-small-en-v1.5",
                         help="Sentence-transformers model to use.")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"[ERROR] Input file not found: {args.input}")

    print(f"[INFO] Loading model: {args.model_name}")
    model = SentenceTransformer(args.model_name)

    records = load_jsonl(args.input)
    print(f"[INFO] Loaded {len(records)} records from {args.input}")

    embeddable = []
    embeddable_texts = []
    skipped = 0

    for record in records:
        text = record.get(args.text_field)
        if not text or not str(text).strip():
            record["embedding"] = None
            skipped += 1
            continue
        embeddable.append(record)
        embeddable_texts.append(str(text))

    print(f"[INFO] {len(embeddable)} records to embed, {skipped} skipped "
          f"(empty/null '{args.text_field}')")

    start_time = time.time()
    embedding_dim = None

    if embeddable_texts:
        vectors = model.encode(
            embeddable_texts,
            batch_size=args.batch_size,
            show_progress_bar=True,
        )
        embedding_dim = vectors.shape[1]

        for record, vector in zip(embeddable, vectors):
            record["embedding"] = vector.tolist()  # numpy array -> JSON-serializable list

    elapsed = time.time() - start_time

    save_jsonl(records, args.output)

    print(f"[DONE] Total records: {len(records)}")
    print(f"[DONE] Embedded: {len(embeddable)}")
    print(f"[DONE] Skipped: {skipped}")
    print(f"[DONE] Embedding dimension: {embedding_dim}")
    print(f"[DONE] Time taken: {elapsed:.2f}s")
    print(f"[DONE] Output written to: {args.output}")


if __name__ == "__main__":
    main()
