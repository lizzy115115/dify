#!/usr/bin/env python3
"""Run inside docker-api-1 to patch parameter-extractor query selectors."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

API_ROOT = Path("/app/api")
if API_ROOT.is_dir() and str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app_factory import create_app
from extensions.ext_database import db
from graphon.nodes.parameter_extractor.entities import ParameterExtractorNodeData
from models.workflow import Workflow
from sqlalchemy import select
from sqlalchemy.orm import Session


def normalize_parameter_extractor_query(graph: dict[str, Any]) -> bool:
    changed = False
    for node in graph.get("nodes", []):
        data = node.get("data", {})
        if data.get("type") != "parameter-extractor":
            continue
        query = data.get("query")
        if (
            isinstance(query, list)
            and len(query) == 1
            and isinstance(query[0], list)
            and len(query[0]) == 2
            and all(isinstance(part, str) for part in query[0])
        ):
            data["query"] = list(query[0])
            changed = True
    return changed


def validate_graph(graph: dict[str, Any]) -> None:
    for node in graph.get("nodes", []):
        data = node.get("data", {})
        if data.get("type") != "parameter-extractor":
            continue
        ParameterExtractorNodeData.model_validate(data)


def patch_app(app_id: str, session: Session) -> dict[str, Any]:
    workflows = session.scalars(select(Workflow).where(Workflow.app_id == app_id)).all()
    if not workflows:
        return {"app_id": app_id, "patched": 0, "error": "no workflows found"}

    patched = 0
    for workflow in workflows:
        graph = dict(workflow.graph_dict)
        if not normalize_parameter_extractor_query(graph):
            continue
        validate_graph(graph)
        workflow.graph = json.dumps(graph, ensure_ascii=False)
        patched += 1

    session.commit()
    return {"app_id": app_id, "patched": patched, "total_workflows": len(workflows)}


def main() -> None:
    app_ids = sys.argv[1:]
    if not app_ids:
        print(json.dumps({"error": "no app ids provided"}))
        sys.exit(1)

    _, app = create_app()
    results: list[dict[str, Any]] = []
    with app.app_context():
        with Session(db.engine, expire_on_commit=False) as session:
            for app_id in app_ids:
                results.append(patch_app(app_id, session))

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
