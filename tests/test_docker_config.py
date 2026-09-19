from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def read(path):
    return path.read_text(encoding="utf-8")


def test_backend_dockerfile_uses_pinned_multistage_build():
    dockerfile = read(ROOT / "Dockerfile")

    assert "FROM python:3.12.9-slim AS builder" in dockerfile
    assert "FROM python:3.12.9-slim AS runtime" in dockerfile
    assert "COPY --from=builder" in dockerfile
    assert "uvicorn" in dockerfile
    assert "app.main:app" in dockerfile


def test_dockerignore_does_not_copy_env():
    content = read(ROOT / ".dockerignore")

    assert ".env" in content
    assert ".venv/" in content
    assert "tests/" in content


def test_frontend_dockerfile_builds_react():
    dockerfile = read(FRONTEND / "Dockerfile")

    assert "FROM node:22-alpine" in dockerfile
    assert "pnpm install --frozen-lockfile" in dockerfile
    assert "pnpm build" in dockerfile
    assert "nginx:alpine" in dockerfile


def test_nginx_proxies_backend_streams():
    config = read(FRONTEND / "nginx.conf")

    assert "proxy_pass http://backend:8000" in config
    assert "proxy_buffering off" in config
    assert "/chat/" in config
    assert "/agent/" in config


def test_compose_defines_services_and_named_volumes():
    compose = read(ROOT / "docker-compose.yml")

    assert "backend:" in compose
    assert "worker:" in compose
    assert "frontend:" in compose
    assert "OPENAI_API_KEY" in compose
    assert "chroma_data:/app/data/chroma" in compose
    assert "postgres_data:/var/lib/postgresql/data" in compose
    assert "./data/chroma:/app/data/chroma" not in compose