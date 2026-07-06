#!/usr/bin/env python3
"""ETL routing: doc_kind / secret_level -> dataset_id."""

from __future__ import annotations

from typing import TypedDict


class DocumentMeta(TypedDict, total=False):
    doc_kind: str
    secret_level: str


DOC_KIND_TO_DATASET_KEY: dict[str, str] = {
    "macro_report": "macro",
    "industry_report": "industry",
    "equity_report": "equity",
    "filing": "filings",
    "regulation": "regulation",
    "internal_report": "internal",
}

DEFAULT_DATASET_KEY = "equity"


def pick_dataset_key(doc: DocumentMeta) -> str:
    if doc.get("secret_level") == "internal":
        return "internal"
    kind = doc.get("doc_kind", "")
    return DOC_KIND_TO_DATASET_KEY.get(kind, DEFAULT_DATASET_KEY)


def pick_dataset_id(doc: DocumentMeta, routing: dict[str, str]) -> str:
    key = pick_dataset_key(doc)
    dataset_id = routing.get(key)
    if not dataset_id:
        raise KeyError(f"No dataset_id mapped for key '{key}'. Run setup_datasets.py first.")
    return dataset_id
