from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture
def compose() -> str:
    return read_text(ROOT / "docker-compose.yml")


@pytest.fixture
def env_example() -> str:
    return read_text(ROOT / ".env.example")


def test_compose_uses_named_volumes_for_runtime_state(compose: str) -> None:
    assert "postgres_data:/var/lib/postgresql/data" in compose
    assert "redis_data:/data" in compose
    assert "chroma_data:/app/data/chroma" in compose
    assert "./data/chroma:/app/data/chroma" not in compose


def test_compose_does_not_expose_database_ports(compose: str) -> None:
    assert '"5432:5432"' not in compose
    assert '"6379:6379"' not in compose
    assert '"6333:6333"' not in compose
    assert '"6334:6334"' not in compose


def test_compose_requires_secrets_before_startup(compose: str) -> None:
    assert "${OPENAI_API_KEY:?OPENAI_API_KEY is required}" in compose
    assert "${JWT_SECRET:?JWT_SECRET is required}" in compose


def test_compose_sets_restart_policy(compose: str) -> None:
    assert "restart: unless-stopped" in compose


def test_compose_waits_for_healthy_dependencies(compose: str) -> None:
    assert "condition: service_healthy" in compose


def test_huggingface_cache_uses_non_root_path(compose: str) -> None:
    assert "hf_cache:/app/.cache/huggingface" in compose
    assert "hf_cache:/root/.cache/huggingface" not in compose


def test_qdrant_uses_pinned_version_and_profile(compose: str) -> None:
    assert "profiles: [\"qdrant\"]" in compose
    assert "qdrant/qdrant:latest" not in compose
    assert "${QDRANT_IMAGE_VERSION:-v1.12.6}" in compose


def test_backend_is_only_published_to_localhost(compose: str) -> None:
    assert "127.0.0.1:${BACKEND_PORT:-8000}:8000" in compose


def test_env_example_declares_new_variables(env_example: str) -> None:
    for variable in [
        "POSTGRES_IMAGE_VERSION=",
        "REDIS_IMAGE_VERSION=",
        "QDRANT_IMAGE_VERSION=",
        "HF_ENDPOINT=",
        "BACKEND_PORT=",
        "FRONTEND_PORT=",
    ]:
        assert variable in env_example