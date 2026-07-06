#!/usr/bin/env python3
"""
Import and publish the banking-research agent workflow to Dify Console.

Credentials (first match wins):
  1. CLI: --email / --password
  2. config.json: console_email / console_password
  3. Env: DIFY_CONSOLE_EMAIL / DIFY_CONSOLE_PASSWORD
  4. Interactive prompt (password only, if email is set)

No password needed when importing via the local Docker API container:
  uv run --project api python scripts/banking-research/deploy_agent_app.py --via-docker

Usage:
  uv run --project api python scripts/banking-research/deploy_agent_app.py --via-docker
  uv run --project api python scripts/banking-research/deploy_agent_app.py --password 'YOUR_PASSWORD'
  DIFY_CONSOLE_PASSWORD=xxx uv run --project api python scripts/banking-research/deploy_agent_app.py
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).parent))

from common import CONFIG_DIR, load_config

DSL_PATH = Path(__file__).parent / "dsl" / "banking-research-agent.generated.yml"
RUNNER_PATH = Path(__file__).parent / "deploy_via_docker_runner.py"
APP_STATE_FILE = CONFIG_DIR / "app_state.json"
DEFAULT_DOCKER_CONTAINER = "docker-api-1"
CONTAINER_YAML_PATH = "/tmp/banking-research-agent.yml"
CONTAINER_RUNNER_PATH = "/tmp/deploy_via_docker_runner.py"
CONTAINER_PATCH_RUNNER_PATH = "/tmp/patch_workflow_query_runner.py"
PATCH_RUNNER_PATH = Path(__file__).parent / "patch_workflow_query_runner.py"
LEGACY_APP_IDS = ["6d977ab0-3bb4-45a0-b2e8-5fc458d3f5b9"]


def encode_password(password: str) -> str:
    return base64.b64encode(password.encode("utf-8")).decode()


def login(client: httpx.Client, console_api_url: str, email: str, password: str) -> dict[str, str]:
    response = client.post(
        f"{console_api_url}/login",
        json={"email": email, "password": encode_password(password), "remember_me": True},
    )
    response.raise_for_status()
    access_token = response.cookies.get("access_token", "")
    csrf_token = response.cookies.get("csrf_token", "")
    if not access_token:
        raise RuntimeError("Login succeeded but access_token cookie missing")
    return {"access_token": access_token, "csrf_token": csrf_token}


def console_headers(cookies: dict[str, str]) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
    }
    if cookies.get("csrf_token"):
        headers["X-CSRF-Token"] = cookies["csrf_token"]
    return headers


def import_app(client: httpx.Client, console_api_url: str, yaml_content: str, cookies: dict[str, str]) -> dict[str, Any]:
    response = client.post(
        f"{console_api_url}/apps/imports",
        json={"mode": "yaml-content", "yaml_content": yaml_content},
        headers=console_headers(cookies),
        cookies=cookies,
    )
    if response.status_code not in (200, 202):
        raise RuntimeError(f"Import failed HTTP {response.status_code}: {response.text}")
    data = response.json()
    if data.get("status") == "failed":
        raise RuntimeError(f"Import failed: {data.get('error')}")
    app_id = data.get("app_id")
    if not app_id:
        raise RuntimeError(f"Import response missing app_id: {json.dumps(data, ensure_ascii=False)}")
    return data


def publish_workflow(client: httpx.Client, console_api_url: str, app_id: str, cookies: dict[str, str]) -> None:
    response = client.post(
        f"{console_api_url}/apps/{app_id}/workflows/publish",
        json={"marked_name": "投研知识库智能体 v1", "marked_comment": "hybrid+Rerank+元数据过滤"},
        headers=console_headers(cookies),
        cookies=cookies,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Publish failed HTTP {response.status_code}: {response.text}")


def load_app_state() -> dict[str, Any] | None:
    if not APP_STATE_FILE.exists():
        return None
    with APP_STATE_FILE.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_app_state(app_id: str, import_data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    state = {
        "app_id": app_id,
        "app_mode": import_data.get("app_mode"),
        "imported_dsl_version": import_data.get("imported_dsl_version"),
        "console_url": f"http://localhost/app/{app_id}/workflow",
    }
    APP_STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"App state saved: {APP_STATE_FILE}")


def resolve_console_credentials(
    config: dict[str, Any],
    *,
    cli_email: str | None,
    cli_password: str | None,
) -> tuple[str, str]:
    email = (
        (cli_email or "").strip()
        or str(config.get("console_email", "")).strip()
        or os.environ.get("DIFY_CONSOLE_EMAIL", "").strip()
    )
    password = (
        (cli_password or "").strip()
        or str(config.get("console_password", "")).strip()
        or os.environ.get("DIFY_CONSOLE_PASSWORD", "").strip()
    )
    if email and not password and sys.stdin.isatty():
        password = getpass.getpass(f"Dify Console password for {email}: ")
    return email, password


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, capture_output=True, text=True)


def deploy_via_docker(
    *,
    email: str,
    dsl_path: Path,
    skip_publish: bool,
    container: str,
    app_id: str | None = None,
) -> dict[str, Any]:
    if not RUNNER_PATH.exists():
        raise RuntimeError(f"Docker runner not found: {RUNNER_PATH}")

    print(f"Copying DSL and runner into {container}...")
    run_command(["docker", "cp", str(dsl_path), f"{container}:{CONTAINER_YAML_PATH}"])
    run_command(["docker", "cp", str(RUNNER_PATH), f"{container}:{CONTAINER_RUNNER_PATH}"])

    cmd = [
        "docker",
        "exec",
        "-w",
        "/app/api",
        container,
        "python3",
        CONTAINER_RUNNER_PATH,
        "--email",
        email,
        "--yaml",
        CONTAINER_YAML_PATH,
    ]
    if skip_publish:
        cmd.append("--skip-publish")
    if app_id:
        cmd.extend(["--app-id", app_id])

    print(f"Importing via AppDslService inside {container} as {email}...")
    result = run_command(cmd)
    output = result.stdout.strip().splitlines()[-1]
    data = json.loads(output)
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data


def patch_deployed_workflows(container: str, app_ids: list[str]) -> None:
    if not PATCH_RUNNER_PATH.exists() or not app_ids:
        return
    run_command(["docker", "cp", str(PATCH_RUNNER_PATH), f"{container}:{CONTAINER_PATCH_RUNNER_PATH}"])
    cmd = ["docker", "exec", "-w", "/app/api", container, "python3", CONTAINER_PATCH_RUNNER_PATH, *app_ids]
    result = run_command(cmd)
    print("Patched parameter-extractor query selectors:")
    print(result.stdout.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy banking research agent to Dify")
    parser.add_argument("--dsl", type=Path, default=DSL_PATH, help="Generated DSL YAML path")
    parser.add_argument("--skip-publish", action="store_true", help="Import only, do not publish workflow")
    parser.add_argument("--email", default=None, help="Dify Console login email")
    parser.add_argument("--password", default=None, help="Dify Console login password")
    parser.add_argument(
        "--via-docker",
        action="store_true",
        help="Import/publish via docker-api-1 AppDslService (no Console password)",
    )
    parser.add_argument(
        "--docker-container",
        default=DEFAULT_DOCKER_CONTAINER,
        help=f"Docker API container name (default: {DEFAULT_DOCKER_CONTAINER})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()

    email, password = resolve_console_credentials(config, cli_email=args.email, cli_password=args.password)
    console_api_url = config.get("console_api_url", "http://localhost/console/api").rstrip("/")

    if not email:
        print(
            "Missing console_email.\n"
            "Set scripts/banking-research/config.json → console_email,\n"
            "or export DIFY_CONSOLE_EMAIL, or pass --email."
        )
        sys.exit(1)

    if not args.dsl.exists():
        print(f"DSL not found: {args.dsl}\nRun generate_agent_app.py first.")
        sys.exit(1)

    if args.via_docker:
        existing_app_id = None
        prior_state = load_app_state()
        if prior_state and prior_state.get("app_id"):
            existing_app_id = str(prior_state["app_id"])
            print(f"Updating existing app: {existing_app_id}")
        import_data = deploy_via_docker(
            email=email,
            dsl_path=args.dsl,
            skip_publish=args.skip_publish,
            container=args.docker_container,
            app_id=existing_app_id,
        )
        app_id = import_data["app_id"]
        print(f"  app_id={app_id} status={import_data.get('status')}")
        if import_data.get("published"):
            print("  published")
        save_app_state(app_id, import_data)
        legacy_ids = [legacy_id for legacy_id in LEGACY_APP_IDS if legacy_id != app_id]
        if legacy_ids:
            patch_deployed_workflows(args.docker_container, legacy_ids)
        print(f"\nOpen: http://localhost/app/{app_id}/workflow")
        return

    if not password:
        print(
            "Missing console_password.\n"
            "Choose one:\n"
            "  1. uv run --project api python scripts/banking-research/deploy_agent_app.py --via-docker\n"
            "  2. Add console_password to scripts/banking-research/config.json\n"
            "  3. export DIFY_CONSOLE_PASSWORD='your-password'\n"
            "  4. uv run --project api python scripts/banking-research/deploy_agent_app.py --password 'your-password'\n"
            "  5. Re-run in an interactive terminal (will prompt for password)"
        )
        sys.exit(1)

    yaml_content = args.dsl.read_text(encoding="utf-8")

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        print(f"Logging in to {console_api_url} as {email}...")
        cookies = login(client, console_api_url, email, password)

        print("Importing workflow DSL...")
        import_data = import_app(client, console_api_url, yaml_content, cookies)
        app_id = import_data["app_id"]
        print(f"  app_id={app_id} status={import_data.get('status')}")

        if not args.skip_publish:
            print("Publishing workflow...")
            publish_workflow(client, console_api_url, app_id, cookies)
            print("  published")

        save_app_state(app_id, import_data)
        print(f"\nOpen: http://localhost/app/{app_id}/workflow")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or str(exc)
        print(f"Docker deploy failed: {detail}")
        sys.exit(1)
    except httpx.HTTPError as exc:
        print(f"HTTP error: {exc}")
        sys.exit(1)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
