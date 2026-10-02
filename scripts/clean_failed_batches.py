#!/usr/bin/env python3
"""Clean failed_batches_deduped.jsonl into valid JSONL records."""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    source = Path("data/reports/failed_batches_deduped.jsonl")
    destination = Path("data/reports/failed_clean.jsonl")

    written = 0
    skipped_blank = 0
    skipped_invalid = 0
    skipped_non_object = 0
    first_errors: list[str] = []

    with source.open("r", encoding="utf-8") as source_file, destination.open("w", encoding="utf-8") as destination_file:
        for line_number, line in enumerate(source_file, 1):
            line = line.strip()
            if not line:
                skipped_blank += 1
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                skipped_invalid += 1
                if len(first_errors) < 10:
                    first_errors.append(f"line {line_number}: invalid JSON: {exc}")
                continue
            if not isinstance(record, dict):
                skipped_non_object += 1
                if len(first_errors) < 10:
                    first_errors.append(f"line {line_number}: non-object JSON type={type(record).__name__}")
                continue
            record.pop("_error", None)
            record.pop("_failed_at", None)
            destination_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    print(f"written={written}")
    print(f"skipped_blank={skipped_blank}")
    print(f"skipped_invalid={skipped_invalid}")
    print(f"skipped_non_object={skipped_non_object}")
    for error in first_errors:
        print(error)


if __name__ == "__main__":
    main()
