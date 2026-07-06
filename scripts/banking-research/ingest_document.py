#!/usr/bin/env python3
"""
Ingest a document into the correct sub-domain dataset with metadata.

Usage:
  uv run --project api python scripts/banking-research/ingest_document.py report.pdf \\
    --meta '{"doc_kind":"equity_report","effective_date":"2026-04-27","ticker":"688256","industry":"国产AI芯片","is_valid":1}'

Optional: pass --dataset-id to override routing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import DifyDatasetClient, build_process_rule, load_config, load_state
from routing import pick_dataset_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest document with hybrid-RAG metadata")
    parser.add_argument("file", type=Path, help="PDF/TXT/DOCX file path")
    parser.add_argument(
        "--meta",
        required=True,
        help='JSON metadata, e.g. \'{"doc_kind":"regulation","is_valid":1,"effective_date":"2024-01-01"}\'',
    )
    parser.add_argument("--dataset-id", help="Override auto-routing dataset_id")
    return parser.parse_args()


def build_document_metadata(
    doc_meta: dict[str, object],
    metadata_field_ids: dict[str, str],
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for name, value in doc_meta.items():
        if name in ("doc_kind", "secret_level"):
            continue
        field_id = metadata_field_ids.get(name)
        if field_id is None:
            print(f"  WARN: unknown metadata field '{name}', skipped")
            continue
        items.append({"id": field_id, "name": name, "value": value})
    return items


def main() -> None:
    args = parse_args()
    if not args.file.exists():
        print(f"File not found: {args.file}")
        sys.exit(1)

    config = load_config()
    state = load_state()
    if state is None:
        print("No datasets_state.json. Run setup_datasets.py first.")
        sys.exit(1)

    doc_meta: dict[str, object] = json.loads(args.meta)
    routing: dict[str, str] = state["routing"]

    if args.dataset_id:
        dataset_id = args.dataset_id
        dataset_key = next((k for k, v in routing.items() if v == dataset_id), "?")
    else:
        dataset_key = None
        from routing import pick_dataset_key

        dataset_key = pick_dataset_key(doc_meta)  # type: ignore[arg-type]
        dataset_id = pick_dataset_id(doc_meta, routing)  # type: ignore[arg-type]

    print(f"Routing -> [{dataset_key}] {dataset_id}")

    client = DifyDatasetClient(config["api_base_url"], config["dataset_api_key"])
    process_rule = build_process_rule(config)

    upload_data = {
        "indexing_technique": "high_quality",
        "process_rule": process_rule,
    }

    print(f"Uploading {args.file.name}...")
    result = client.create_document_by_file(dataset_id, args.file, upload_data)
    document = result.get("document") or {}
    document_id = document.get("id")
    batch = result.get("batch")
    print(f"  document_id={document_id}  batch={batch}")

    metadata_items = build_document_metadata(doc_meta, state["metadata_field_ids"].get(dataset_key, {}))
    if document_id and metadata_items:
        print("Setting document metadata...")
        client.update_documents_metadata(
            dataset_id,
            [{"document_id": document_id, "metadata_list": metadata_items}],
        )
        print("  metadata OK")

    print("\nTrack indexing:")
    print(f"  GET {config['api_base_url']}/datasets/{dataset_id}/documents/{batch}/indexing-status")


if __name__ == "__main__":
    main()
