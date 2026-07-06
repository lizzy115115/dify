#!/usr/bin/env python3
"""
Batch hit-testing for hybrid + Rerank validation.

Usage:
  uv run --project api python scripts/banking-research/hit_test.py
  uv run --project api python scripts/banking-research/hit_test.py --dataset regulation
  uv run --project api python scripts/banking-research/hit_test.py --queries queries.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import DifyDatasetClient, load_config, load_state

DEFAULT_QUERIES: list[dict[str, str]] = [
    {"dataset": "equity", "query": "2024年三季度招商银行净利润同比增速"},
    {"dataset": "regulation", "query": "商业银行资本管理办法 2024 生效日期"},
    {"dataset": "macro", "query": "2024年中国GDP增速预测"},
    {"dataset": "filings", "query": "贵州茅台2023年报营业收入"},
    {"dataset": "industry", "query": "新能源汽车行业2024年渗透率"},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hit test hybrid + Rerank retrieval")
    parser.add_argument("--dataset", help="Only test one dataset key (macro/industry/...)")
    parser.add_argument("--queries", type=Path, help="JSON file: [{\"dataset\":\"equity\",\"query\":\"...\"}]")
    parser.add_argument("--top", type=int, default=5, help="Print top N hits per query")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()
    state = load_state()
    if state is None:
        print("No datasets_state.json. Run setup_datasets.py first.")
        sys.exit(1)

    routing: dict[str, str] = state["routing"]
    retrieval_model = state["retrieval_model"]

    queries = DEFAULT_QUERIES
    if args.queries:
        with args.queries.open(encoding="utf-8") as handle:
            queries = json.load(handle)

    if args.dataset:
        queries = [q for q in queries if q["dataset"] == args.dataset]
        if not queries:
            print(f"No queries for dataset '{args.dataset}'")
            sys.exit(1)

    client = DifyDatasetClient(config["api_base_url"], config["dataset_api_key"])

    print("=== Hit Testing (hybrid_search + Rerank) ===\n")
    for item in queries:
        key = item["dataset"]
        query = item["query"]
        dataset_id = routing.get(key)
        if not dataset_id:
            print(f"[{key}] SKIP: no dataset_id in routing")
            continue

        print(f"[{key}] query: {query}")
        try:
            result = client.hit_test(dataset_id, query, retrieval_model)
        except Exception as exc:
            print(f"  FAILED: {exc}\n")
            continue

        records = result.get("records") or []
        for idx, record in enumerate(records[: args.top], start=1):
            score = record.get("score", 0)
            content = (record.get("segment") or {}).get("content", "")[:120]
            print(f"  #{idx} score={score:.4f}  {content}...")
        print(f"  total hits: {len(records)}\n")


if __name__ == "__main__":
    main()
