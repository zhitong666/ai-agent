# AI Job Agent

一个用于解析招聘 JD、检索岗位知识，并生成岗位分析和学习建议的 AI Agent 项目。

## 技术栈

- Python
- FastAPI
- Pydantic
- DeepSeek API
- sentence-transformers
- numpy
- chromadb

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
- POST /chat

## 检索 CLI

uv run python -m app.rag_cli "AI Agent 需要哪些技能"

### /chat 示例

请求：

POST /chat
Content-Type: application/json

{
  "session_id": "s1",
  "question": "FastAPI 需要掌握什么"
}

响应：

{
  "reply": "...",
  "sources": [
    {
      "chunk_id": "doc-fastapi-0",
      "title": "FastAPI 后端开发",
      "text": "...",
      "score": 0.8
    }
  ]
}

## RAG 评估

uv run python -m app.eval_cli --top-k 3

## 向量持久化

向量和元数据持久化在 data/chroma/，重启服务后不会重新 Embedding。