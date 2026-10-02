#!/usr/bin/env python3
"""
tag_and_summarize.py
--------------------
Batch tags and summarizes cleaned JSONL documents using an LLM.

Schema supported (fields already present, tagging fields populated by this script):
  {
    id, source_type, title, raw_text, source_url, published_date,
    scraped_category, word_count, content_hash, links, scraped_at,
    subfield_tag: null, entities: null, relates_to_topics: null,
    summary: null, embedding: null, kg_node_id: null
  }

CLI arguments:
  --input               Path to cleaned input JSONL file (required)
  --output              Path to write tagged output JSONL file (required)
    --model               Model identifier (default: "anthropic/claude-haiku-4.5")
  --provider            Provider choices: "openrouter", "anthropic" (default: "openrouter")
  --max-chars-per-item  Truncate raw_text to this length before sending (default: 3000)
  --batch-char-budget   Target character budget per batch (default: 12000)
    --failed-batches      Path to log failed batches (default: "data/reports/failed_batches.jsonl")
  --delay               Delay in seconds between batches (default: 1.0)
  --save-every          Save progress to output every N batches (default: 20)
  --print-every         Print progress every N batches (default: 10)
  --dry-run             Run batching and validation using mock responses (no API calls)

Usage:
    # Default production model:
    python tag_and_summarize.py --input data/cleaned/TDScleaned_data.jsonl --output data/tagged/TDStagged_data.jsonl

    # Explicit model override:
    python tag_and_summarize.py --input data/cleaned/TDScleaned_data.jsonl --output data/tagged/TDStagged_data.jsonl \
      --model anthropic/claude-haiku-4.5

"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, List, Optional


# ── Environment & .env loader ────────────────────────────────────────────────

def load_dotenv_if_present(env_path: Path | str = ".env") -> None:
    """Load key-value pairs from .env into os.environ if not already set."""
    p = Path(env_path)
    if not p.is_file():
        # Check parent directory as fallback
        parent_p = Path(__file__).resolve().parent / ".env"
        if parent_p.is_file():
            p = parent_p
        else:
            return

    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


# ── Batching Logic ───────────────────────────────────────────────────────────

def pack_batches(
    items: list[dict[str, Any]],
    max_chars_per_item: int,
    batch_char_budget: int,
) -> list[list[dict[str, Any]]]:
    """
    Batching logic (source-agnostic, no per-source-type branching):
    1. Truncate each item's raw_text to max_chars_per_item BEFORE packing.
    2. Iterate items, accumulating them into a batch until adding the next
       item would exceed batch_char_budget total characters; then flush
       that batch as one API call and start a new batch. A single item
       larger than the budget becomes its own one-item batch.
    """
    batches: list[list[dict[str, Any]]] = []
    current_batch: list[dict[str, Any]] = []
    current_chars = 0

    for item in items:
        raw_text = item.get("raw_text") or ""
        item_chars = len(raw_text[:max_chars_per_item])

        # If adding this item would exceed the budget, flush current batch
        if current_batch and (current_chars + item_chars > batch_char_budget):
            batches.append(current_batch)
            current_batch = []
            current_chars = 0

        # If current batch is empty and this item alone meets or exceeds budget
        if not current_batch and item_chars >= batch_char_budget:
            batches.append([item])
        else:
            current_batch.append(item)
            current_chars += item_chars

    if current_batch:
        batches.append(current_batch)

    return batches


# ── Prompt Construction ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert AI/data-science taxonomist and technical summarizer.
You will receive a numbered list of technical documents (course material, articles, or
research papers) with their titles and text.

For each document provided, extract:

- subfield: string — MUST be exactly one of this fixed list, chosen for best fit.
  Do not invent new subfield names outside this list:
  ["Natural Language Processing", "Computer Vision", "Reinforcement Learning",
   "Generative AI", "Machine Learning Systems & MLOps", "Data Engineering",
   "Data Visualization", "Web Scraping & Automation", "Software Engineering & APIs",
   "Cloud & Deployment", "Databases & SQL", "LLM Tooling & Prompt Engineering",
   "AI Safety & Alignment", "Robotics", "Multimodal AI", "Other"]

- entities: array of strings, MAXIMUM 5, most important only
  (named tools/models/libraries/platforms/organizations,
  e.g. ["PyTorch", "Docker", "OpenAI", "FastAPI", "Supabase"])

- relates_to_topics: array of strings, MAXIMUM 5, most important only
  (core technical concepts, lowercase, prefer standard terminology over
  paraphrased variants — e.g. "transformers" not "Transformer models",
  "retrieval augmented generation" not "RAG systems",
  e.g. ["containerization", "fine-tuning", "retrieval augmented generation",
  "prompt engineering"])

- summary: string — a concise 2-3 sentence summary in original phrasing
  capturing the core message or content

EDGE CASES:
If a document's content is insufficient to classify meaningfully (too short,
boilerplate, navigation text, etc.), still return a complete object: set
subfield to "Other", entities and relates_to_topics to empty arrays [], and
summary to a brief one-sentence note of what the document appears to be.
Never omit or skip an object for any input document, regardless of content quality.

CRITICAL INSTRUCTIONS:
1. You MUST respond with a valid JSON array of objects.
2. The JSON array must contain EXACTLY the same number of objects as input
   documents, in the EXACT same order (from document 1 to N).
3. Output ONLY the raw JSON array. Do not include Markdown code blocks
   (```json ... ```), preamble, or commentary.
"""


def build_user_prompt(batch: list[dict[str, Any]], max_chars_per_item: int) -> str:
    """Build numbered list of {title, raw_text} pairs using truncated text."""
    lines = [
        f"Analyze the following {len(batch)} document(s) and return a JSON array with exactly {len(batch)} objects in matching order:\n"
    ]
    for idx, item in enumerate(batch, 1):
        title = item.get("title") or "Untitled"
        raw_text = (item.get("raw_text") or "")[:max_chars_per_item]
        lines.append(f"--- Document [{idx}] ---")
        lines.append(f"Title: {title}")
        lines.append(f"Text: {raw_text}\n")
    return "\n".join(lines)


# ── JSON Response Extraction & Validation ────────────────────────────────────

def parse_llm_json_response(raw_text: str, expected_count: int) -> list[dict[str, Any]]:
    """
    Parses LLM response into a list of dictionaries matching expected_count.
    Handles raw JSON, markdown code fences, and wrapped dictionary outputs.
    Raises ValueError on invalid JSON or length mismatch.
    """
    text = raw_text.strip()

    # Strip markdown code fence if present
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    data: Any = None

    # Attempt 1: Direct JSON load
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: Extract substring between outermost [ and ]
    if data is None:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

    # Attempt 3: If wrapped in an object { ... }, try parsing that
    if data is None:
        start_obj = text.find("{")
        end_obj = text.rfind("}")
        if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
            try:
                data = json.loads(text[start_obj : end_obj + 1])
            except json.JSONDecodeError:
                pass

    if data is None:
        snippet = (raw_text[:200] + "...") if len(raw_text) > 200 else raw_text
        raise ValueError(f"Could not parse valid JSON from model response: {snippet}")

    # If the model wrapped the list inside a dict (e.g. {"results": [...]} or {"documents": [...]})
    if isinstance(data, dict):
        for val in data.values():
            if isinstance(val, list) and len(val) == expected_count:
                data = val
                break
        else:
            # Special case: expected_count == 1 and model returned a single object instead of array
            if expected_count == 1 and ("subfield" in data or "summary" in data or "entities" in data):
                data = [data]

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array (list), got {type(data).__name__}")

    if len(data) != expected_count:
        raise ValueError(f"Array length mismatch: expected {expected_count} items, got {len(data)}")

    return data


# ── Merging Logic ────────────────────────────────────────────────────────────

def merge_result_into_record(record: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """
    Merge tagging result back into record fields:
    - subfield_tag
    - entities
    - relates_to_topics
    - summary
    embedding and kg_node_id stay null.
    """
    subfield = (
        result.get("subfield")
        or result.get("subfield_tag")
        or "Artificial Intelligence"
    )
    if not isinstance(subfield, str):
        subfield = str(subfield)

    entities = result.get("entities")
    if entities is None:
        entities = []
    elif isinstance(entities, str):
        entities = [e.strip() for e in entities.split(",") if e.strip()]
    elif not isinstance(entities, list):
        entities = [str(entities)]

    relates_to_topics = result.get("relates_to_topics") or result.get("topics")
    if relates_to_topics is None:
        relates_to_topics = []
    elif isinstance(relates_to_topics, str):
        relates_to_topics = [t.strip() for t in relates_to_topics.split(",") if t.strip()]
    elif not isinstance(relates_to_topics, list):
        relates_to_topics = [str(relates_to_topics)]

    summary = result.get("summary") or ""
    if not isinstance(summary, str):
        summary = str(summary)

    # Clone record to avoid mutating original
    merged = dict(record)
    merged["subfield_tag"] = subfield
    merged["entities"] = entities
    merged["relates_to_topics"] = relates_to_topics
    merged["summary"] = summary
    merged["embedding"] = None
    merged["kg_node_id"] = None
    return merged


# ── API Client (OpenAI SDK with fallback to standard urllib) ─────────────────

class OpenRouterClient:
    """
    Client for OpenRouter's OpenAI-compatible completions endpoint.
    Prefers the `openai` Python package if installed; otherwise falls back to
    standard library `urllib.request` with zero third-party dependencies.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 90.0,
        max_output_tokens: int = 4096,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens
        self._openai_client = None

        try:
            from openai import OpenAI  # type: ignore
            self._openai_client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
            )
        except ImportError:
            self._openai_client = None

    def call(self, messages: list[dict[str, str]]) -> str:
        """Sends chat completion request and returns string response content."""
        if self._openai_client is not None:
            # Use official OpenAI client
            response = self._openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=self.max_output_tokens,
            )
            choice = response.choices[0]
            return choice.message.content or ""
        else:
            # Fallback to standard library urllib.request
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": self.max_output_tokens,
            }
            req_body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/shubhamrazzsharma/ai_news_agent",
                    "X-Title": "AI News Agent Tagging",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    choice = resp_data["choices"][0]
                    return choice["message"]["content"] or ""
            except urllib.error.HTTPError as http_err:
                err_content = http_err.read().decode("utf-8", errors="replace")
                hint = ""
                if http_err.code == 404:
                    hint = f"\n[Hint] The model slug '{self.model}' may not be available on OpenRouter. Consider using '--model anthropic/claude-haiku-4.5' or another available model."
                raise RuntimeError(
                    f"OpenRouter HTTP {http_err.code} ({http_err.reason}): {err_content}{hint}"
                ) from http_err


def mock_model_call(batch: list[dict[str, Any]]) -> str:
    """Mock model response for offline development and testing (--dry-run)."""
    results = []
    for item in batch:
        title = item.get("title") or "Technical Document"
        results.append({
            "subfield": "Data Science & AI Tools",
            "entities": ["Python", "Linux", "VS Code"],
            "relates_to_topics": ["command line", "environment setup", "developer tooling"],
            "summary": f"This document discusses concepts related to {title}. It provides foundational knowledge and practical instructions for software and AI workflows.",
        })
    return json.dumps(results)


# ── File I/O Helpers ─────────────────────────────────────────────────────────

def append_records_to_jsonl(path: Path | str, records: list[dict[str, Any]]) -> None:
    """Appends records to a JSONL file, creating parent directories if needed."""
    if not records:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()


def log_failed_batch(path: Path | str, batch: list[dict[str, Any]], error_msg: str) -> None:
    """
    Logs failed batch records to failed_batches.jsonl.
    Stores records matching the JSONL schema so they can be re-run directly.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        for item in batch:
            record_copy = dict(item)
            record_copy["_error"] = error_msg
            record_copy["_failed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            f.write(json.dumps(record_copy, ensure_ascii=False) + "\n")
        f.flush()


# ── Main Processing Pipeline ─────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tag and summarize cleaned JSONL records using an LLM via OpenRouter.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to cleaned input JSONL file.",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Path to write tagged output JSONL file.",
    )
    parser.add_argument(
        "--model", "-m",
        default="anthropic/claude-haiku-4.5",
        help="Model identifier on OpenRouter (default: anthropic/claude-haiku-4.5).",
    )
    parser.add_argument(
        "--provider",
        choices=["openrouter", "anthropic"],
        default="openrouter",
        help="LLM provider (default: openrouter; all calls route through OpenRouter OpenAI-compatible client).",
    )
    parser.add_argument(
        "--max-chars-per-item",
        type=int,
        default=3000,
        help="Truncate any single item's raw_text to this length before sending.",
    )
    parser.add_argument(
        "--batch-char-budget",
        type=int,
        default=12000,
        help="Target character budget per batch across accumulated items.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=4096,
        help="Maximum tokens to generate per batch (default: 4096).",
    )
    parser.add_argument(
        "--failed-batches",
        default="data/reports/failed_batches.jsonl",
        help="Path to log items from failed batches.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between batches.",
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=20,
        help="Save progress to --output incrementally every N batches.",
    )
    parser.add_argument(
        "--print-every",
        type=int,
        default=10,
        help="Print progress every N batches.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run batching, packaging, and saving using mock LLM responses (no external API calls).",
    )

    args = parser.parse_args()

    # Load environment variables from .env if present
    load_dotenv_if_present()

    input_path = Path(args.input)
    output_path = Path(args.output)
    failed_batches_path = Path(args.failed_batches)

    if not input_path.is_file():
        sys.exit(f"Error: Input file does not exist: {input_path}")

    # Determine API key
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key and args.provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key and not args.dry_run:
        sys.exit(
            "Error: OPENROUTER_API_KEY environment variable is not set.\n"
            "Please set OPENROUTER_API_KEY in your environment or in a .env file.\n"
            "(To test without API calls, use the --dry-run flag)."
        )

    # Read and parse input JSONL
    print(f"Reading input records from {input_path}...")
    items: list[dict[str, Any]] = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                items.append(record)
            except json.JSONDecodeError as err:
                print(f"[WARN] Skipping invalid JSON at line {line_num}: {err}")

    total_records = len(items)
    print(f"Loaded {total_records} valid records.")
    if total_records == 0:
        print("No records to process. Exiting.")
        return

    # Pack items into batches according to character budget
    batches = pack_batches(
        items,
        max_chars_per_item=args.max_chars_per_item,
        batch_char_budget=args.batch_char_budget,
    )
    total_batches = len(batches)
    print(
        f"Packed {total_records} records into {total_batches} batches "
        f"(max {args.max_chars_per_item} chars/item, budget {args.batch_char_budget} chars/batch)."
    )

    # Prepare output file (initialize/truncate for clean run)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        pass  # Initialize empty file

    client: Optional[OpenRouterClient] = None
    if not args.dry_run:
        client = OpenRouterClient(
            api_key=api_key or "",
            model=args.model,
            max_output_tokens=args.max_output_tokens,
        )
        print(f"Using model: {args.model} via OpenRouter API client.")
    else:
        print("Running in DRY-RUN mode (mock LLM responses).")

    pending_records: list[dict[str, Any]] = []
    processed_count = 0
    successful_count = 0
    failed_count = 0

    print("-" * 60)
    for batch_idx, batch in enumerate(batches):
        batch_num = batch_idx + 1
        batch_size = len(batch)
        user_prompt = build_user_prompt(batch, args.max_chars_per_item)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Execution with 1 retry on error or invalid response
        success = False
        parsed_results: Optional[list[dict[str, Any]]] = None
        last_error = ""

        for attempt in (1, 2):
            try:
                if args.dry_run:
                    raw_response = mock_model_call(batch)
                else:
                    assert client is not None
                    raw_response = client.call(messages)

                parsed_results = parse_llm_json_response(raw_response, expected_count=batch_size)
                success = True
                break
            except Exception as exc:
                last_error = str(exc)
                if attempt == 1:
                    print(
                        f"[WARN] Batch {batch_num}/{total_batches} attempt 1 failed: {exc}. Retrying once..."
                    )
                    time.sleep(2.0)
                else:
                    print(
                        f"[ERROR] Batch {batch_num}/{total_batches} failed after retry: {exc}. "
                        f"Logging {batch_size} records to {failed_batches_path}"
                    )

        if success and parsed_results is not None:
            for record, res in zip(batch, parsed_results):
                merged = merge_result_into_record(record, res)
                pending_records.append(merged)
            successful_count += batch_size
        else:
            log_failed_batch(failed_batches_path, batch, error_msg=last_error)
            failed_count += batch_size

        processed_count += batch_size

        # Print progress every 10 batches
        if batch_num % args.print_every == 0:
            print(f"Processed {processed_count}/{total_records} records")

        # Save progress to --output incrementally every 20 batches
        if batch_num % args.save_every == 0:
            append_records_to_jsonl(output_path, pending_records)
            print(
                f"[INFO] Incremental save: wrote {len(pending_records)} records to {output_path} (Batch {batch_num}/{total_batches})"
            )
            pending_records = []

        # 1 second delay between batches
        if batch_num < total_batches and args.delay > 0:
            time.sleep(args.delay)

    # Final flush of any remaining pending records
    if pending_records:
        append_records_to_jsonl(output_path, pending_records)
        print(f"[INFO] Final save: wrote {len(pending_records)} records to {output_path}")
        pending_records = []

    # Final completion print
    print("-" * 60)
    print(f"Processed {processed_count}/{total_records} records (Completed)")
    print(
        f"Summary: {successful_count} successfully tagged, "
        f"{failed_count} failed."
    )
    if failed_count > 0:
        print(f"Failed records logged to: {failed_batches_path}")
    print(f"Tagged output written to: {output_path}")


if __name__ == "__main__":
    main()
