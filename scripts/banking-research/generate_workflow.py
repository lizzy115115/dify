#!/usr/bin/env python3
"""
Generate importable workflow DSL with real dataset UUIDs from setup state.

Usage:
  uv run --project api python scripts/banking-research/generate_workflow.py
  uv run --project api python scripts/banking-research/generate_workflow.py --llm gpt-4o --llm-provider langgenius/openai/openai

Import in Console: Studio -> Import DSL -> upload generated YAML
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import load_config, load_state

TEMPLATE_PATH = Path(__file__).parent / "dsl" / "banking-research-rag.template.yml"
OUTPUT_PATH = Path(__file__).parent / "dsl" / "banking-research-rag.generated.yml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate workflow DSL for hybrid + Rerank + metadata")
    parser.add_argument("--llm", default="gpt-4o", help="LLM model for rewrite + answer nodes")
    parser.add_argument("--llm-provider", default="langgenius/openai/openai", help="LLM provider")
    parser.add_argument("-o", "--output", type=Path, default=OUTPUT_PATH, help="Output YAML path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()
    state = load_state()
    if state is None:
        print("No datasets_state.json. Run setup_datasets.py first.")
        sys.exit(1)

    public_ids = state.get("public_dataset_ids") or []
    if not public_ids:
        routing = state.get("routing", {})
        public_ids = [
            routing[k] for k in ("macro", "industry", "equity", "filings", "regulation") if k in routing
        ]

    if not public_ids:
        print("No public dataset IDs in state.")
        sys.exit(1)

    retrieval = config["retrieval"]
    node_ids = {
        "__START_ID__": "1000000000001",
        "__REWRITE_ID__": "1000000000002",
        "__RETRIEVAL_ID__": "1000000000003",
        "__ANSWER_ID__": "1000000000004",
        "__END_ID__": "1000000000005",
    }

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    content = template
    for placeholder, value in node_ids.items():
        content = content.replace(placeholder, value)

    dataset_yaml = "\n".join(f"        - {did}" for did in public_ids)
    content = content.replace("__DATASET_IDS__", dataset_yaml)
    content = content.replace("__RERANK_MODEL__", config["reranking_model"])
    content = content.replace("__RERANK_PROVIDER__", config["reranking_provider"])
    content = content.replace("__LLM_MODEL__", args.llm)
    content = content.replace("__LLM_PROVIDER__", args.llm_provider)
    content = content.replace("__TOP_K__", str(retrieval["top_k"]))
    content = content.replace("__SCORE_THRESHOLD__", str(retrieval["score_threshold"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")

    print(f"Generated: {args.output}")
    print(f"  datasets: {len(public_ids)}")
    print(f"  rerank:   {config['reranking_provider']}/{config['reranking_model']}")
    print(f"  llm:      {args.llm_provider}/{args.llm}")
    print("\nImport: Dify Console -> Studio -> Import DSL")


if __name__ == "__main__":
    main()
