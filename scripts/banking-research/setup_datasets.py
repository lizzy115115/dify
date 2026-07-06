#!/usr/bin/env python3
"""
Create 6 sub-domain datasets with hybrid_search + Rerank + metadata schema.

Prerequisites:
  - VECTOR_STORE=milvus, MILVUS_ENABLE_HYBRID_SEARCH=true (before any dataset creation)
  - Xinference (or other provider) has bge-m3 + bge-reranker-v2-m3 configured in Dify
  - config.json copied from config.example.json with valid dataset_api_key

Usage:
  uv run --project api python scripts/banking-research/setup_datasets.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import (
    DifyDatasetClient,
    build_retrieval_model,
    load_config,
    save_state,
)


def main() -> None:
    config = load_config()
    client = DifyDatasetClient(config["api_base_url"], config["dataset_api_key"])
    retrieval_model = build_retrieval_model(config)

    routing: dict[str, str] = {}
    metadata_ids: dict[str, dict[str, str]] = {}

    print("=== Creating 6 sub-domain datasets (hybrid + Rerank) ===\n")

    for spec in config["datasets"]:
        key = spec["key"]
        print(f"[{key}] Creating '{spec['name']}'...")

        payload = {
            "name": spec["name"],
            "description": spec["description"],
            "indexing_technique": "high_quality",
            "permission": spec["permission"],
            "embedding_model": config["embedding_model"],
            "embedding_model_provider": config["embedding_model_provider"],
            "retrieval_model": retrieval_model,
        }

        try:
            result = client.create_dataset(payload)
        except Exception as exc:
            print(f"  FAILED: {exc}")
            sys.exit(1)

        dataset_id = result["id"]
        routing[key] = dataset_id
        print(f"  OK  dataset_id={dataset_id}")

        metadata_ids[key] = {}
        for field in config["metadata_fields"]:
            try:
                meta_result = client.create_metadata_field(dataset_id, field)
                metadata_ids[key][field["name"]] = meta_result["id"]
                print(f"  metadata '{field['name']}' -> {meta_result['id']}")
            except Exception as exc:
                print(f"  metadata '{field['name']}' FAILED: {exc}")

    state = {
        "routing": routing,
        "metadata_field_ids": metadata_ids,
        "retrieval_model": retrieval_model,
        "public_dataset_ids": [
            routing[k] for k in ("macro", "industry", "equity", "filings", "regulation") if k in routing
        ],
    }
    save_state(state)

    print("\n=== Done ===")
    print("Next steps:")
    print("  1. ingest:  uv run --project api python scripts/banking-research/ingest_document.py <file> --meta '{...}'")
    print("  2. hit test: uv run --project api python scripts/banking-research/hit_test.py")
    print("  3. workflow: uv run --project api python scripts/banking-research/generate_workflow.py")


if __name__ == "__main__":
    main()
