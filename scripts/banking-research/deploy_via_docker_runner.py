#!/usr/bin/env python3
"""
Run inside docker-api-1 to import and publish the banking-research agent DSL.

Usage (from host, via deploy_agent_app.py --via-docker):
  docker exec -w /app/api docker-api-1 python3 /tmp/deploy_via_docker_runner.py \\
    --email admin@example.com --yaml /tmp/banking-research-agent.yml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

API_ROOT = Path("/app/api")
if API_ROOT.is_dir() and str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app_factory import create_app
from extensions.ext_database import db
from libs.datetime_utils import naive_utc_now
from models.model import App
from services.account_service import AccountService
from services.app_dsl_service import AppDslService
from services.entities.dsl_entities import ImportMode, ImportStatus
from services.workflow_service import WorkflowService
from sqlalchemy.orm import Session, sessionmaker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import/publish agent DSL inside docker-api")
    parser.add_argument("--email", required=True, help="Dify admin account email")
    parser.add_argument("--yaml", required=True, type=Path, help="Path to DSL YAML inside container")
    parser.add_argument("--app-id", default=None, help="Update existing app instead of creating a new one")
    parser.add_argument("--skip-publish", action="store_true")
    parser.add_argument("--marked-name", default="投研知识库智能体 v1")
    parser.add_argument("--marked-comment", default="hybrid+Rerank+元数据过滤")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.yaml.exists():
        print(json.dumps({"error": f"YAML not found: {args.yaml}"}, ensure_ascii=False))
        sys.exit(1)

    yaml_content = args.yaml.read_text(encoding="utf-8")
    _, app = create_app()

    with app.app_context():
        with Session(db.engine, expire_on_commit=False) as session:
            account = AccountService.get_account_by_email_with_case_fallback(args.email.strip())
            if account is None:
                print(json.dumps({"error": f"Account not found: {args.email}"}, ensure_ascii=False))
                sys.exit(1)

            loaded = AccountService.load_user(account.id)
            if loaded is None:
                print(json.dumps({"error": f"Account has no workspace: {args.email}"}, ensure_ascii=False))
                sys.exit(1)
            account = loaded

            dsl_service = AppDslService(session)
            result = dsl_service.import_app(
                account=account,
                import_mode=ImportMode.YAML_CONTENT,
                yaml_content=yaml_content,
                app_id=args.app_id,
            )

            if result.status == ImportStatus.PENDING:
                result = dsl_service.confirm_import(import_id=result.id, account=account)

            if result.status == ImportStatus.FAILED:
                session.rollback()
                print(
                    json.dumps(
                        {"error": result.error or "Import failed", "status": str(result.status)},
                        ensure_ascii=False,
                    )
                )
                sys.exit(1)

            session.commit()

            app_id = result.app_id
            if not app_id:
                print(json.dumps({"error": "Import response missing app_id"}, ensure_ascii=False))
                sys.exit(1)

            published = False
            if not args.skip_publish:
                workflow_service = WorkflowService()
                with sessionmaker(db.engine).begin() as pub_session:
                    app_model = pub_session.get(App, app_id)
                    if app_model is None:
                        print(json.dumps({"error": f"App not found after import: {app_id}"}, ensure_ascii=False))
                        sys.exit(1)

                    workflow = workflow_service.publish_workflow(
                        session=pub_session,
                        app_model=app_model,
                        account=account,
                        marked_name=args.marked_name,
                        marked_comment=args.marked_comment,
                    )
                    app_model.workflow_id = workflow.id
                    app_model.updated_by = account.id
                    app_model.updated_at = naive_utc_now()
                published = True

        print(
            json.dumps(
                {
                    "app_id": app_id,
                    "app_mode": result.app_mode,
                    "imported_dsl_version": result.imported_dsl_version,
                    "status": str(result.status),
                    "published": published,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
