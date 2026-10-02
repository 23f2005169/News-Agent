#!/usr/bin/env python3
"""
clean_jsonl.py
--------------
Universal cleaning script for scraped JSONL files.

Reads any raw JSONL file (read-only) and writes cleaned data with
the canonical schema required by the AI News Agent ingestion pipeline:
  id, source_type, title, raw_text, source_url, published_date,
  scraped_category, word_count, content_hash, links, scraped_at,
  subfield_tag, entities, relates_to_topics, summary, embedding,
  kg_node_id

Transformations applied:
  1. HTML tags stripped from content → raw_text
  2. Whitespace normalised (consecutive spaces/newlines → single space)
  3. Records with raw_text < min_text_len (default: 50 chars) are dropped
  4. Deduplication on content_hash (first occurrence wins)

Usage:
    # Clean default file (data/raw/tds_pages.jsonl -> data/cleaned/TDScleaned_data.jsonl)
  python scripts/clean_jsonl.py

    # Clean specific file (defaults output under data/cleaned/)
  python scripts/clean_jsonl.py arxiv_pages.jsonl

  # Clean with explicit output path
  python scripts/clean_jsonl.py arxiv_pages.jsonl cleaned_arxiv.jsonl

  # Specify source_type explicitly (e.g. paper, course_portal, news, tool)
  python scripts/clean_jsonl.py arxiv_pages.jsonl -o cleaned_arxiv.jsonl --source-type paper
"""

import argparse
import hashlib
import json
import re
import sys
import uuid
from pathlib import Path

# Base directory (project root: parent of scripts/)
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = "data/raw/tds_pages.jsonl"
DEFAULT_OUTPUT = "data/cleaned/TDScleaned_data.jsonl"
MIN_TEXT_LEN = 50


# ── HTML / whitespace helpers ────────────────────────────────────────────

_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)
_SPACE_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    """Remove HTML tags and decode common HTML entities."""
    text = _TAG_RE.sub(" ", text)
    text = (text
            .replace("&amp;",  "&")
            .replace("&lt;",   "<")
            .replace("&gt;",   ">")
            .replace("&quot;", '"')
            .replace("&#39;",  "'")
            .replace("&nbsp;", " "))
    return text


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace runs to a single space and strip edges."""
    return _SPACE_RE.sub(" ", text).strip()


def clean_text(raw: str) -> str:
    return normalize_whitespace(strip_html(raw))


# ── Path & argument resolution ───────────────────────────────────────────

def resolve_path(path_str: str | None, default_name: str, for_output: bool = False, input_stem: str = "") -> Path:
    """Resolve a file path universally from CWD or BASE_DIR."""
    if not path_str:
        if for_output and input_stem:
            stem = input_stem.lower()
            if "arxiv" in stem:
                default_name = "data/cleaned/arxiv_cleaned_data.jsonl"
            elif "tds" in stem:
                default_name = "data/cleaned/TDScleaned_data.jsonl"
            else:
                default_name = f"data/cleaned/{input_stem}_cleaned_data.jsonl"
        if Path.cwd().name == "scripts":
            return BASE_DIR / default_name
        return Path.cwd() / default_name

    p = Path(path_str)
    if p.is_absolute():
        return p

    # If it exists relative to current working directory, use it
    cwd_path = Path.cwd() / p
    if cwd_path.exists():
        return cwd_path

    # If it exists relative to BASE_DIR (project root), use it
    repo_path = BASE_DIR / p
    if repo_path.exists():
        return repo_path

    # If creating an output file that does not exist yet:
    if Path.cwd().name == "scripts":
        return BASE_DIR / p
    return cwd_path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Clean raw JSONL and transform to canonical schema."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help=f"Input JSONL file (default: {DEFAULT_INPUT})"
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Output JSONL file (default: cleaned_<input_stem>.jsonl or cleaned_data.jsonl)"
    )
    parser.add_argument(
        "-i", "--input-path",
        dest="flag_input",
        default=None,
        help="Explicit flag for input JSONL file"
    )
    parser.add_argument(
        "-o", "--output-path",
        dest="flag_output",
        default=None,
        help="Explicit flag for output JSONL file"
    )
    parser.add_argument(
        "--source-type",
        default=None,
        help="Literal source_type (e.g. 'course_portal', 'paper', 'news', 'tool'). Inferred if omitted."
    )
    parser.add_argument(
        "--min-text-len",
        type=int,
        default=MIN_TEXT_LEN,
        help=f"Minimum raw_text length to keep (default: {MIN_TEXT_LEN})"
    )
    return parser.parse_args()


# ── Record builder ───────────────────────────────────────────────────────

def infer_source_type(input_path: Path, src: dict, override_type: str | None = None) -> str:
    """Infer source_type from CLI flag, input filename, or raw record content."""
    if override_type:
        return override_type

    stem = input_path.stem.lower()
    if "arxiv" in stem or "paper" in stem:
        return "paper"
    if "tds" in stem or "course" in stem:
        return "course_portal"
    if "article" in stem:
        return "article"
    if "tool" in stem or "github" in stem:
        return "tool"

    # Check raw record
    if "source_type" in src and src["source_type"]:
        return str(src["source_type"])

    src_val = str(src.get("source", "")).lower()
    if "arxiv" in src_val:
        return "paper"
    if "course" in src_val or "tds" in src_val:
        return "course_portal"

    return "course_portal"


def build_record(src: dict, raw_text: str, source_type: str) -> dict:
    content_hash = src.get("content_hash")
    if not content_hash and raw_text:
        content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    word_count = src.get("word_count")
    if word_count is None:
        word_count = len(raw_text.split())

    return {
        "id":                src.get("id") or str(uuid.uuid4()),
        "source_type":       source_type,
        "title":             src.get("title", ""),
        "raw_text":          raw_text,
        "source_url":        src.get("url") or src.get("source_url", ""),
        "published_date":    src.get("published_date", None),
        "scraped_category":  src.get("category") or src.get("scraped_category", ""),
        "word_count":        word_count,
        "content_hash":      content_hash or "",
        "links":             src.get("links", []),
        "scraped_at":        src.get("scraped_at", ""),
        # Fields to be populated in later pipeline stages
        "subfield_tag":      None,
        "entities":          None,
        "relates_to_topics": None,
        "summary":           None,
        "embedding":         None,
        "kg_node_id":        None,
    }


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    input_str = args.flag_input or args.input
    input_path = resolve_path(input_str, DEFAULT_INPUT)

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_str = args.flag_output or args.output
    output_path = resolve_path(output_str, DEFAULT_OUTPUT, for_output=True, input_stem=input_path.stem)

    min_text_len = args.min_text_len

    # Counters
    total_read      = 0
    dropped_parse   = 0
    dropped_short   = 0
    dropped_dedup   = 0
    written         = 0

    seen_hashes: set[str] = set()

    print(f"Reading       : {input_path}")
    print(f"Writing to    : {output_path}")
    print(f"Min text len  : {min_text_len}")
    print("-" * 65)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(input_path,  "r", encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:

        for line_num, raw_line in enumerate(fin, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            total_read += 1

            # ── 1. Parse ───────────────────────────────────────────────
            try:
                src = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                dropped_parse += 1
                print(f"  [PARSE ERROR] line {line_num}: {exc}")
                continue

            # ── 2. Determine source_type ───────────────────────────────
            source_type = infer_source_type(input_path, src, args.source_type)

            # ── 3. Clean raw_text ──────────────────────────────────────
            raw_content = src.get("content") or src.get("raw_text") or src.get("text") or ""
            raw_text    = clean_text(str(raw_content))

            # ── 4. Drop short records ──────────────────────────────────
            if len(raw_text) < min_text_len:
                dropped_short += 1
                print(
                    f"  [DROPPED — too short] line {line_num} | "
                    f"id={src.get('id', '?')} | "
                    f"len={len(raw_text)}"
                )
                continue

            # ── 5. Deduplicate on content_hash ─────────────────────────
            content_hash = src.get("content_hash")
            if not content_hash and raw_text:
                content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

            if content_hash and content_hash in seen_hashes:
                dropped_dedup += 1
                print(
                    f"  [DROPPED — duplicate] line {line_num} | "
                    f"id={src.get('id', '?')} | "
                    f"hash={content_hash[:16]}…"
                )
                continue

            if content_hash:
                seen_hashes.add(content_hash)

            # ── 6. Build and write cleaned record ──────────────────────
            record = build_record(src, raw_text, source_type)
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    # ── Summary ──────────────────────────────────────────────────────────
    print("-" * 65)
    print(f"Total records read   : {total_read}")
    print(f"Dropped — parse err  : {dropped_parse}")
    print(f"Dropped — too short  : {dropped_short}")
    print(f"Dropped — duplicate  : {dropped_dedup}")
    print(f"Records written      : {written}")
    print(f"\n✅ Output saved to: {output_path}")


if __name__ == "__main__":
    main()
