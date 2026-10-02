#!/usr/bin/env python3
"""
audit_jsonl.py
--------------
Universal audit script for JSONL files.

Reads any JSONL file (read-only) and produces:
  1. Per-key stats: presence count, null/empty count, data types seen
  2. Sample pretty-printed records
  3. Lines that fail JSON parsing (with line numbers)
  4. Summary: total records, file size, avg text length

Output goes to stdout AND is saved as a JSON audit report.

Usage:
    # Audit default file (data/raw/tds_pages.jsonl -> data/reports/TDSaudit_report.json)
  python scripts/audit_jsonl.py

    # Audit any specific file (auto-names report under data/reports/)
  python scripts/audit_jsonl.py arxiv_pages.jsonl

  # Audit with custom output report path
  python scripts/audit_jsonl.py arxiv_pages.jsonl -o arxiv_audit_report.json

  # Audit with custom sample count and text field
  python scripts/audit_jsonl.py my_data.jsonl --samples 5 --text-field raw_text
"""

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

# Base directory (project root: parent of scripts/)
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = "data/raw/tds_pages.jsonl"
DEFAULT_REPORT = "data/reports/TDSaudit_report.json"


def resolve_path(path_str: str | None, default_name: str, for_output: bool = False, input_stem: str = "") -> Path:
    """Resolve a file path universally from CWD or BASE_DIR."""
    if not path_str:
        if for_output and input_stem:
            stem = input_stem.lower()
            if "arxiv" in stem:
                default_name = "data/reports/arxiv_audit_report.json"
            elif "tds" in stem:
                default_name = "data/reports/TDSaudit_report.json"
            else:
                default_name = f"data/reports/{input_stem}_audit_report.json"
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
        description="Audit a JSONL file and produce a JSON report + console summary."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help=f"Path to input JSONL file (default: {DEFAULT_INPUT})"
    )
    parser.add_argument(
        "-i", "--input-path",
        dest="flag_input",
        default=None,
        help="Explicit flag for input JSONL file"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Path to output JSON report file (default: <input_stem>_audit_report.json or audit_report.json)"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=3,
        help="Number of sample records to display (default: 3)"
    )
    parser.add_argument(
        "--text-field",
        default="content",
        help="Field name for text length statistics (default: content, fallback to raw_text/text)"
    )
    return parser.parse_args()


def _is_null_or_empty(value):
    """Return True for None, empty string, empty list, empty dict."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def _type_label(value):
    """Human-friendly type name."""
    if value is None:
        return "null"
    return type(value).__name__


def audit(path: Path, text_field: str = "content", num_samples: int = 3):
    file_size_bytes = path.stat().st_size

    records: list[dict] = []
    parse_errors: list[dict] = []

    # Key-level accumulators
    key_presence: dict[str, int] = defaultdict(int)
    key_null_empty: dict[str, int] = defaultdict(int)
    key_types: dict[str, set[str]] = defaultdict(set)

    text_lengths: list[int] = []

    # ── Pass 1: read every line ────────────────────────────────────────
    with open(path, "r", encoding="utf-8") as fh:
        for line_num, raw_line in enumerate(fh, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue  # skip blank lines

            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                parse_errors.append(
                    {"line": line_num, "error": str(exc), "raw": raw_line[:200]}
                )
                continue

            records.append(record)

            # Per-key stats
            for key, value in record.items():
                key_presence[key] += 1
                key_types[key].add(_type_label(value))
                if _is_null_or_empty(value):
                    key_null_empty[key] += 1

            # Text-length accumulator (with smart fallback if custom text_field missing)
            text_val = record.get(text_field)
            if text_val is None and text_field == "content":
                text_val = record.get("raw_text") or record.get("text")

            if isinstance(text_val, str):
                text_lengths.append(len(text_val))

    total_records = len(records)

    # ── Per-key report ─────────────────────────────────────────────────
    all_keys = sorted(key_presence.keys())
    key_report = {}
    for key in all_keys:
        key_report[key] = {
            "present_count": key_presence[key],
            "missing_count": total_records - key_presence[key],
            "null_or_empty_count": key_null_empty.get(key, 0),
            "data_types": sorted(key_types[key]),
        }

    # ── Samples ────────────────────────────────────────────────────────
    if total_records <= num_samples:
        samples = records
    else:
        random.seed(42)  # reproducible
        samples = random.sample(records, num_samples)

    # ── Summary ────────────────────────────────────────────────────────
    avg_text_len = (
        round(sum(text_lengths) / len(text_lengths), 1) if text_lengths else 0
    )
    summary = {
        "total_records": total_records,
        "file_size_bytes": file_size_bytes,
        "file_size_mb": round(file_size_bytes / (1024 * 1024), 2),
        "unique_keys": len(all_keys),
        f"avg_{text_field}_length_chars": avg_text_len,
        "parse_error_count": len(parse_errors),
    }

    # ── Build full report dict ─────────────────────────────────────────
    report = {
        "summary": summary,
        "key_stats": key_report,
        "parse_errors": parse_errors,
        "sample_records": samples,
    }

    return report


def print_report(report: dict, text_field: str = "content"):
    """Pretty-print the audit to stdout."""
    sep = "=" * 70

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n{sep}")
    print("  JSONL AUDIT REPORT")
    print(sep)
    s = report["summary"]
    avg_len_key = f"avg_{text_field}_length_chars"
    avg_val = s.get(avg_len_key, 0)
    print(f"  Total records      : {s['total_records']}")
    print(f"  File size          : {s['file_size_mb']} MB  ({s['file_size_bytes']} bytes)")
    print(f"  Unique keys        : {s['unique_keys']}")
    print(f"  Avg {text_field} length : {avg_val} chars")
    print(f"  Parse errors       : {s['parse_error_count']}")
    print(sep)

    # ── Per-key stats ──────────────────────────────────────────────────
    print("\n📊 PER-KEY STATISTICS\n")
    header = f"  {'Key':<20} {'Present':>8} {'Missing':>8} {'Null/Empty':>11}  Types"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for key, info in report["key_stats"].items():
        types_str = ", ".join(info["data_types"])
        print(
            f"  {key:<20} {info['present_count']:>8} "
            f"{info['missing_count']:>8} "
            f"{info['null_or_empty_count']:>11}  {types_str}"
        )

    # ── Parse errors ───────────────────────────────────────────────────
    if report["parse_errors"]:
        print(f"\n⚠️  PARSE ERRORS ({len(report['parse_errors'])} lines failed)\n")
        for err in report["parse_errors"]:
            print(f"  Line {err['line']}: {err['error']}")
            print(f"    Preview: {err['raw'][:120]}…")
    else:
        print("\n✅ No JSON parse errors detected.\n")

    # ── Sample records ─────────────────────────────────────────────────
    print(f"\n📝 SAMPLE RECORDS ({len(report['sample_records'])} shown)\n")
    for i, rec in enumerate(report["sample_records"], 1):
        print(f"  ── Sample {i} {'─' * 55}")
        # Truncate long text fields for console readability
        display = {}
        for k, v in rec.items():
            if isinstance(v, str) and len(v) > 300:
                display[k] = v[:300] + f"… [{len(v)} chars total]"
            elif isinstance(v, list) and len(v) > 10:
                display[k] = v[:10] + [f"… {len(v)} items total"]
            else:
                display[k] = v
        print(json.dumps(display, indent=4, ensure_ascii=False))
    print()


def main():
    args = parse_args()
    input_str = args.flag_input or args.input
    input_path = resolve_path(input_str, DEFAULT_INPUT)

    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = resolve_path(args.output, DEFAULT_REPORT, for_output=True, input_stem=input_path.stem)

    print(f"Auditing     : {input_path}")
    print(f"Report target: {output_path}")

    report = audit(input_path, text_field=args.text_field, num_samples=args.samples)

    # Print to console
    print_report(report, text_field=args.text_field)

    # Save JSON report (samples stored in full, not truncated)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, default=str)
    print(f"💾 Full audit report saved to: {output_path}\n")


if __name__ == "__main__":
    main()
