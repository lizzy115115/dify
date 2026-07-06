#!/usr/bin/env python3
"""Shared helpers for banking-research hybrid + Rerank + metadata setup."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TypedDict

import httpx

CONFIG_DIR = Path(__file__).parent / "config"
STATE_FILE = CONFIG_DIR / "datasets_state.json"


class RetrievalConfig(TypedDict):
    search_method: str
    top_k: int
    score_threshold_enabled: bool
    score_threshold: float
    reranking_enable: bool
    reranking_mode: str


class ChunkingConfig(TypedDict):
    mode: str
    max_tokens: int
    chunk_overlap: int
    separator: str


class MetadataField(TypedDict):
    type: str
    name: str


class DatasetSpec(TypedDict):
    key: str
    name: str
    description: str
    permission: str


class BankingResearchConfig(TypedDict):
    api_base_url: str
    dataset_api_key: str
    embedding_model: str
    embedding_model_provider: str
    reranking_model: str
    reranking_provider: str
    retrieval: RetrievalConfig
    chunking: ChunkingConfig
    metadata_fields: list[MetadataField]
    datasets: list[DatasetSpec]


def load_config(path: Path | None = None) -> BankingResearchConfig:
    config_path = path or Path(__file__).parent / "config.json"
    if not config_path.exists():
        example = Path(__file__).parent / "config.example.json"
        print(f"Missing {config_path}. Copy {example} to config.json and fill in dataset_api_key.")
        sys.exit(1)
    with config_path.open(encoding="utf-8") as handle:
        config: BankingResearchConfig = json.load(handle)
    api_key = config.get("dataset_api_key", "")
    if not api_key or api_key.startswith("dataset-xxx"):
        print(
            "Invalid dataset_api_key in config.json.\n"
            "Create one in Dify console: Settings → API Keys → Create → Dataset API,\n"
            "then paste the key (format: dataset-...) into config.json."
        )
        sys.exit(1)
    return config


def save_state(state: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, ensure_ascii=False)
    print(f"State saved to {STATE_FILE}")


def load_state() -> dict[str, Any] | None:
    if not STATE_FILE.exists():
        return None
    with STATE_FILE.open(encoding="utf-8") as handle:
        return json.load(handle)


class DifyDatasetClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def create_dataset(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(self._url("/datasets"), headers=self._headers, json=payload)
            response.raise_for_status()
            return response.json()

    def create_metadata_field(self, dataset_id: str, field: MetadataField) -> dict[str, Any]:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                self._url(f"/datasets/{dataset_id}/metadata"),
                headers=self._headers,
                json=field,
            )
            response.raise_for_status()
            return response.json()

    def hit_test(self, dataset_id: str, query: str, retrieval_model: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                self._url(f"/datasets/{dataset_id}/hit-testing"),
                headers=self._headers,
                json={"query": query, "retrieval_model": retrieval_model},
            )
            response.raise_for_status()
            return response.json()

    def update_documents_metadata(
        self, dataset_id: str, operation_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                self._url(f"/datasets/{dataset_id}/documents/metadata"),
                headers=self._headers,
                json={"operation_data": operation_data},
            )
            response.raise_for_status()
            return response.json()

    def create_document_by_file(
        self,
        dataset_id: str,
        file_path: Path,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        with httpx.Client(timeout=300.0) as client:
            with file_path.open("rb") as handle:
                response = client.post(
                    self._url(f"/datasets/{dataset_id}/document/create-by-file"),
                    headers={"Authorization": self._headers["Authorization"]},
                    files={"file": (file_path.name, handle)},
                    data={"data": json.dumps(data, ensure_ascii=False)},
                )
            response.raise_for_status()
            return response.json()


def build_retrieval_model(config: BankingResearchConfig) -> dict[str, Any]:
    retrieval = config["retrieval"]
    return {
        "search_method": retrieval["search_method"],
        "reranking_enable": retrieval["reranking_enable"],
        "reranking_mode": retrieval["reranking_mode"],
        "reranking_model": {
            "reranking_provider_name": config["reranking_provider"],
            "reranking_model_name": config["reranking_model"],
        },
        "top_k": retrieval["top_k"],
        "score_threshold_enabled": retrieval["score_threshold_enabled"],
        "score_threshold": retrieval["score_threshold"],
    }


def build_process_rule(config: BankingResearchConfig) -> dict[str, Any]:
    chunking = config["chunking"]
    return {
        "mode": chunking["mode"],
        "rules": {
            "pre_processing_rules": [{"id": "remove_extra_spaces", "enabled": True}],
            "segmentation": {
                "separator": chunking["separator"],
                "max_tokens": chunking["max_tokens"],
                "chunk_overlap": chunking["chunk_overlap"],
            },
        },
    }
