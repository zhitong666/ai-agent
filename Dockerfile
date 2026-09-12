FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY app ./app
COPY data ./data

RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --no-install-project

EXPOSE 8000

CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]