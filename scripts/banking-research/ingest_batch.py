#!/usr/bin/env python3
"""
Batch ingest all PDFs listed in docs/data/manifest.json.

Usage:
  uv run --project api python scripts/banking-research/ingest_batch.py
  uv run --project api python scripts/banking-research/ingest_batch.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "docs" / "data"
MANIFEST = DATA_DIR / "manifest.json"
INGEST_SCRIPT = Path(__file__).parent / "ingest_document.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch ingest docs/data PDFs from manifest.json")
    parser.add_argument("--manifest", type=Path, default=MANIFEST, help="Path to manifest.json")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.manifest.exists():
        print(f"Manifest not found: {args.manifest}")
        sys.exit(1)

    entries: list[dict[str, object]] = json.loads(args.manifest.read_text(encoding="utf-8"))
    print(f"=== Batch ingest ({len(entries)} files) ===\n")

    failed = 0
    for index, entry in enumerate(entries, start=1):
        rel_path = str(entry["file"])
        file_path = DATA_DIR / rel_path
        meta = entry["meta"]
        meta_json = json.dumps(meta, ensure_ascii=False)

        print(f"[{index}/{len(entries)}] {rel_path}")
        if not file_path.exists():
            print(f"  SKIP: file not found")
            failed += 1
            continue

        cmd = [
            sys.executable,
            str(INGEST_SCRIPT),
            str(file_path),
            "--meta",
            meta_json,
        ]
        if args.dry_run:
            print(f"  DRY-RUN: {' '.join(cmd)}")
            continue

        result = subprocess.run(cmd, cwd=REPO_ROOT)
        if result.returncode != 0:
            print(f"  FAILED (exit {result.returncode})")
            failed += 1

    if args.dry_run:
        print(f"\nDry-run complete ({len(entries)} files).")
        return
    if failed:
        print(f"\nDone with {failed} failure(s).")
        sys.exit(1)
    print("\nAll files ingested successfully.")


if __name__ == "__main__":
    main()
