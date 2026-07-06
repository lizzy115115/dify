#!/usr/bin/env python3
"""Audit knowledge base indexing + hit-test for demo queries."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import DifyDatasetClient, load_config, load_state

QUERIES_PATH = Path(__file__).parent / "queries" / "verify_demo_queries.json"

DATASET_LABELS = {
    "macro": "宏观策略库",
    "industry": "行业研究库",
    "equity": "个股研报库",
    "filings": "财报公告库",
    "regulation": "监管政策库",
    "internal": "内部研究库",
}


def main() -> None:
    config = load_config()
    state = load_state()
    if state is None:
        print("Run setup_datasets.py first.")
        sys.exit(1)

    routing = state["routing"]
    retrieval_model = state["retrieval_model"]
    client = DifyDatasetClient(config["api_base_url"], config["dataset_api_key"])

    queries = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))

    print("=== Knowledge Base Audit (Hit Test) ===\n")
    print(f"score_threshold={retrieval_model.get('score_threshold')}  top_k={retrieval_model.get('top_k')}\n")

    ok_count = 0
    for item in queries:
        key = item["dataset"]
        query = item["query"]
        dataset_id = routing[key]
        label = DATASET_LABELS.get(key, key)
        try:
            result = client.hit_test(dataset_id, query, retrieval_model)
            records = result.get("records") or []
            top_score = records[0].get("score", 0) if records else 0
            status = "OK" if records and top_score >= retrieval_model.get("score_threshold", 0.52) else "WEAK/EMPTY"
            if status == "OK":
                ok_count += 1
            print(f"[{status}] [{label}] {query}")
            print(f"       hits={len(records)} top_score={top_score:.4f}")
            if records:
                seg = records[0].get("segment") or {}
                print(f"       top_segment_id={seg.get('id','?')[:36]}")
                print(f"       preview={seg.get('content','')[:100].replace(chr(10),' ')}...")
            print()
        except Exception as exc:
            print(f"[FAIL] [{label}] {query}")
            print(f"       {exc}\n")

    print(f"Summary: {ok_count}/{len(queries)} queries pass score_threshold\n")


if __name__ == "__main__":
    main()
