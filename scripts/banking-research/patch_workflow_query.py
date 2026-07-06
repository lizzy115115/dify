#!/usr/bin/env python3
"""
Patch parameter-extractor query selectors inside docker-api-1.

Fixes legacy DSL shape:
  query: [['2000000000001', 'query']]  ->  query: ['2000000000001', 'query']

Usage:
  uv run --project api python scripts/banking-research/patch_workflow_query.py
  uv run --project api python scripts/banking-research/patch_workflow_query.py --app-id 6d977ab0-...
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

RUNNER_PATH = Path(__file__).parent / "patch_workflow_query_runner.py"
DEFAULT_CONTAINER = "docker-api-1"
CONTAINER_RUNNER_PATH = "/tmp/patch_workflow_query_runner.py"
DEFAULT_APP_IDS = [
    "b7ba6809-de49-42cb-84d5-79149e415f55",
    "6d977ab0-3bb4-45a0-b2e8-5fc458d3f5b9",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch parameter-extractor query in deployed workflows")
    parser.add_argument(
        "--app-id",
        action="append",
        dest="app_ids",
        help="App UUID to patch (repeatable). Defaults to known banking-research apps.",
    )
    parser.add_argument("--docker-container", default=DEFAULT_CONTAINER)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app_ids = args.app_ids or DEFAULT_APP_IDS

    subprocess.run(
        ["docker", "cp", str(RUNNER_PATH), f"{args.docker_container}:{CONTAINER_RUNNER_PATH}"],
        check=True,
    )

    cmd = [
        "docker",
        "exec",
        "-w",
        "/app/api",
        args.docker_container,
        "python3",
        CONTAINER_RUNNER_PATH,
        *app_ids,
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)


if __name__ == "__main__":
    main()
