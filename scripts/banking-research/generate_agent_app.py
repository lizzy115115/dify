#!/usr/bin/env python3
"""
Generate production banking-research agent workflow DSL.

Usage:
  uv run --project api python scripts/banking-research/generate_agent_app.py
  uv run --project api python scripts/banking-research/generate_agent_app.py \\
    --llm qwen-plus --llm-provider langgenius/tongyi/tongyi
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent_dsl_builder import build_app_dsl, dump_yaml
from common import load_config, load_state

OUTPUT_PATH = Path(__file__).parent / "dsl" / "banking-research-agent.generated.yml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate banking research agent workflow DSL")
    parser.add_argument("--llm", default=None, help="LLM model (default from config.json llm_model)")
    parser.add_argument("--llm-provider", default=None, help="LLM provider (default from config.json)")
    parser.add_argument("-o", "--output", type=Path, default=OUTPUT_PATH, help="Output YAML path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()
    state = load_state()
    if state is None:
        print("No datasets_state.json. Run setup_datasets.py first.")
        sys.exit(1)

    routing = state.get("routing")
    if not routing:
        print("No routing in datasets_state.json.")
        sys.exit(1)

    llm_model = args.llm or config.get("llm_model", "qwen-plus")
    llm_provider = args.llm_provider or config.get("llm_provider", "langgenius/tongyi/tongyi")
    retrieval = config["retrieval"]

    dsl = build_app_dsl(
        routing,
        llm_provider=llm_provider,
        llm_model=llm_model,
        rerank_provider=config["reranking_provider"],
        rerank_model=config["reranking_model"],
        top_k=retrieval["top_k"],
        score_threshold=retrieval["score_threshold"],
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(dump_yaml(dsl), encoding="utf-8")

    print(f"Generated: {args.output}")
    print(f"  nodes:    13 (extract → rewrite → classify → 5×retrieval → agg → answer → compliance)")
    print(f"  llm:      {llm_provider}/{llm_model}")
    print(f"  rerank:   {config['reranking_provider']}/{config['reranking_model']}")
    print(f"  datasets: {len(state.get('public_dataset_ids', []))} public libraries")
    print("\nNext: uv run --project api python scripts/banking-research/deploy_agent_app.py")


if __name__ == "__main__":
    main()
