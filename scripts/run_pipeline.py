#!/usr/bin/env python3
"""
run_pipeline.py

Single entry point: raw scraped JSONL -> cleaned -> tagged+summarized ->
embedded -> pushed to Supabase. Calls each existing script as a subprocess,
in order, passing one stage's --output as the next stage's --input.

Works for any source — pass --source-type matching whichever adapter
exists in clean_jsonl.py (course_portal, paper, article, tool, news, ...).

Usage:
    python scripts/run_pipeline.py --input data/raw/tds_blog_pages.jsonl --source-type article
    python scripts/run_pipeline.py --input data/raw/arxiv_pages.jsonl --source-type arxiv --model anthropic/claude-haiku-4.5
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


def run_stage(description: str, cmd: list[str]) -> None:
    print(f"\n=== {description} ===")
    print(" ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(f"[ERROR] Stage failed: {description} (exit code {result.returncode})")


def main():
    parser = argparse.ArgumentParser(description="Run the full ingestion pipeline end to end.")
    parser.add_argument("--input", required=True, type=Path, help="Raw scraped JSONL.")
    parser.add_argument("--source-type", required=True,
                         help="Must match the source-type logic in clean_jsonl.py (e.g. course_portal, paper, article).")
    parser.add_argument("--work-dir", type=Path, default=Path("data/tmp"),
                         help="Where intermediate stage files are written.")
    parser.add_argument("--model", default="anthropic/claude-haiku-4.5",
                         help='Tagging model. Default is Claude Haiku 4.5.')
    parser.add_argument("--table", default="items", help="Supabase table to push into.")
    parser.add_argument("--max-batches", type=int, default=None,
                         help="Limit tagging batches — useful for a quick dry run of the whole chain.")
    parser.add_argument("--keep-intermediate", action="store_true",
                         help="Keep stage files in --work-dir instead of relying on them being temporary.")
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"[ERROR] Input file not found: {args.input}")

    args.work_dir.mkdir(parents=True, exist_ok=True)
    stem = args.input.stem
    scripts_dir = Path(__file__).resolve().parent

    cleaned_path = args.work_dir / f"{stem}_cleaned.jsonl"
    tagged_path = args.work_dir / f"{stem}_tagged.jsonl"
    embedded_path = args.work_dir / f"{stem}_embedded.jsonl"

    start = time.time()

    run_stage("1/4 Clean", [
        sys.executable, str(scripts_dir / "clean_jsonl.py"),
        "--input", str(args.input),
        "--output", str(cleaned_path),
        "--source-type", args.source_type,
    ])

    tag_cmd = [
        sys.executable, str(scripts_dir / "tag_and_summarize.py"),
        "--input", str(cleaned_path),
        "--output", str(tagged_path),
        "--model", args.model,
    ]
    if args.max_batches:
        tag_cmd += ["--max-batches", str(args.max_batches)]
    run_stage("2/4 Tag + summarize", tag_cmd)

    run_stage("3/4 Generate embeddings", [
        sys.executable, str(scripts_dir / "generate_embeddings.py"),
        "--input", str(tagged_path),
        "--output", str(embedded_path),
    ])

    run_stage("4/4 Push to Supabase", [
        sys.executable, str(scripts_dir / "push_to_supabase.py"),
        "--input", str(embedded_path),
        "--table", args.table,
    ])

    elapsed = time.time() - start
    print(f"\n[DONE] Full pipeline finished in {elapsed:.1f}s")
    print(f"[DONE] Source: {args.source_type} | Input: {args.input} | Table: {args.table}")

    if not args.keep_intermediate:
        for path in (cleaned_path, tagged_path, embedded_path):
            if path.exists():
                path.unlink()
        print(f"[INFO] Removed intermediate files from {args.work_dir}")
    else:
        print(f"[INFO] Kept intermediate files in {args.work_dir}")


if __name__ == "__main__":
    main()