from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture
def ci_workflow() -> str:
    return read_text(WORKFLOWS / "ci.yml")


@pytest.fixture
def deploy_workflow() -> str:
    return read_text(WORKFLOWS / "deploy.yml")


def test_ci_workflow_runs_backend_lint_and_tests(ci_workflow: str) -> None:
    assert "uv sync --frozen --all-groups" in ci_workflow
    assert "uv run ruff check ." in ci_workflow
    assert "uv run pytest -q" in ci_workflow


def test_ci_workflow_uses_ci_test_environment(ci_workflow: str) -> None:
    assert "APP_ENV: test" in ci_workflow
    assert "OPENAI_API_KEY: sk-ci-test-key" in ci_workflow
    assert "JWT_SECRET: ci-secret-at-least-32-characters-long" in ci_workflow


def test_ci_workflow_runs_frontend_checks_and_build(ci_workflow: str) -> None:
    assert "pnpm install --frozen-lockfile" in ci_workflow
    assert "pnpm lint" in ci_workflow
    assert "pnpm test" in ci_workflow
    assert "pnpm build" in ci_workflow


def test_ci_workflow_builds_docker_images(ci_workflow: str) -> None:
    assert "docker compose config -q" in ci_workflow
    assert "docker compose build backend worker frontend" in ci_workflow


def test_deploy_workflow_uses_manual_dispatch_and_ssh(
    deploy_workflow: str,
) -> None:
    assert "workflow_dispatch" in deploy_workflow
    assert "secrets.DEPLOY_HOST" in deploy_workflow
    assert "secrets.DEPLOY_SSH_KEY" in deploy_workflow
    assert "docker compose up -d --build" in deploy_workflow