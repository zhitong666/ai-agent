from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture
def dockerfile() -> str:
    return read_text(ROOT / "Dockerfile")


@pytest.fixture
def dockerignore() -> str:
    return read_text(ROOT / ".dockerignore")


def test_dockerfile_uses_pinned_python_and_slim(dockerfile: str) -> None:
    assert "FROM python:3.12.9-slim AS builder" in dockerfile
    assert "FROM python:3.12.9-slim AS runtime" in dockerfile


def test_dockerfile_pins_uv_and_skips_dev_dependencies(dockerfile: str) -> None:
    assert "ARG UV_VERSION=0.12.5" in dockerfile
    assert "pip install" in dockerfile
    assert "--index-url https://pypi.tuna.tsinghua.edu.cn/simple" in dockerfile
    assert "uv sync --frozen --no-dev --no-install-project" in dockerfile


def test_dockerfile_runs_as_non_root_user(dockerfile: str) -> None:
    assert "groupadd --system app" in dockerfile
    assert "useradd --system --gid app" in dockerfile
    assert "USER app" in dockerfile


def test_dockerfile_has_healthcheck(dockerfile: str) -> None:
    assert "HEALTHCHECK" in dockerfile
    assert "http://127.0.0.1:8000/health" in dockerfile


def test_dockerignore_blocks_secrets_and_runtime_state(dockerignore: str) -> None:
    expected_patterns = [
        ".env",
        ".venv/",
        "tests/",
        "data/chroma/",
        "data/qdrant_storage/",
        "data/postgres/",
        "data/redis/",
        "data/*.sqlite",
        "data/eval_set.json",
    ]

    for pattern in expected_patterns:
        assert pattern in dockerignore