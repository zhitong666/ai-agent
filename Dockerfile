FROM python:3.12.9-slim AS builder

ARG UV_VERSION=0.12.5

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install \
    --no-cache-dir \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    "uv==${UV_VERSION}" \
    && uv sync --frozen --no-dev --no-install-project

FROM python:3.12.9-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app --create-home --home-dir /app app \
    && mkdir -p \
        /app/.cache/huggingface \
        /app/data/chroma \
        /app/data/shared_memory \
        /app/data/langgraph_checkpoints \
    && chown -R app:app /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app app /app/app
COPY --chown=app:app migrations /app/migrations
COPY --chown=app:app data/knowledge_base.json /app/data/knowledge_base.json

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]