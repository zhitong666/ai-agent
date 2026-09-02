# AI Job Agent

一个用于解析招聘 JD、检索岗位知识，并生成岗位分析和学习建议的 AI Agent 项目。

## 技术栈

- Python
- FastAPI
- Pydantic
- DeepSeek API
- sentence-transformers
- numpy

## 环境配置

复制 `.env.example` 为 `.env`，然后填写：

OPENAI_API_KEY=你的DeepSeek密钥
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com

## 安装依赖

uv add fastapi "uvicorn[standard]" pydantic openai python-dotenv sentence-transformers numpy
uv add --dev pytest httpx

## 运行测试

uv run pytest

## 启动服务

uv run uvicorn app.main:app --reload

## 接口

- GET /health
- POST /jd/parse
- POST /jd/analyze

## 检索 CLI

uv run python -m app.rag_cli "AI Agent 需要哪些技能"