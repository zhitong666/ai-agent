import os

from pydantic import BaseModel, Field

from app.function_calling import call_required_function
from app.model_registry import get_model_name
from app.structured_output import build_tool_parameters_from_model


class RewrittenQuery(BaseModel):
    rewritten_query: str = Field(
        ...,
        min_length=1,
        description="优化后的主检索查询",
    )
    sub_queries: list[str] = Field(
        default_factory=list,
        description="补充查询，最多 3 个",
    )
    reason: str = Field(
        default="",
        description="为什么这样改写",
    )


QUERY_REWRITE_SYSTEM_PROMPT = """你是检索查询改写器。
把用户的问题改写成更适合 RAG 检索的形式。

要求：
1. rewritten_query 必须包含明确的关键词，不能太口语化。
2. 如果原问题可能涉及多个知识点，用 sub_queries 补充不同角度。
3. 不要编造用户没提到的信息。
4. 必须调用 rewrite_query 工具。"""

QUERY_REWRITE_TOOL = {
    "type": "function",
    "function": {
        "name": "rewrite_query",
        "description": "保存查询改写结果",
        "parameters": build_tool_parameters_from_model(RewrittenQuery),
    },
}


def build_rewrite_messages(question: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": QUERY_REWRITE_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": f"用户问题：{question}",
        },
    ]


def fallback_rewrite(question: str) -> RewrittenQuery:
    return RewrittenQuery(
        rewritten_query=question,
        sub_queries=[],
        reason="查询改写不可用，使用原始问题降级",
    )


def rewrite_query(
    client,
    question: str,
    model_name: str | None = None,
    max_attempts: int = 2,
) -> RewrittenQuery:
    model_name = model_name or get_model_name(
        "chat",
        os.getenv("OPENAI_MODEL")
    )

    return call_required_function(
        client,
        build_rewrite_messages(question),
        [QUERY_REWRITE_TOOL],
        "rewrite_query",
        RewrittenQuery,
        model_name=model_name,
        max_attempts=max_attempts,
    )


def rewrite_query_safe(
    client,
    question: str,
    model_name: str | None = None,
    max_attempts: int = 2,
) -> RewrittenQuery:
    try:
        return rewrite_query(
            client,
            question,
            model_name=model_name,
            max_attempts=max_attempts,
        )
    except Exception as exc:
        plan = fallback_rewrite(question)
        plan.reason = f"{plan.reason}: {exc}"
        return plan


def merge_retrieval_results(
    results_by_query: list[list[dict]],
    top_k: int,
) -> list[dict]:
    merged: dict[str, dict] = {}

    for results in results_by_query:
        for item in results:
            doc = item["doc"]
            chunk_id = doc.get("chunk_id", doc.get("id", "unknown"))
            score = float(item["score"])

            if chunk_id not in merged or score > merged[chunk_id]["score"]:
                merged[chunk_id] = {
                    "doc": doc,
                    "score": score,
                }

    return sorted(
        merged.values(),
        key=lambda item: item["score"],
        reverse=True,
    )[:top_k]


def multi_query_retrieve(
    retriever,
    question: str,
    top_k: int = 3,
    client=None,
    rewrite_fn=None,
    enable_rewrite: bool = True,
    rewrite_model_name: str | None = None,
) -> list[dict]:
    if rewrite_fn is not None:
        plan = rewrite_fn(question)
    elif enable_rewrite and client is not None:
        plan = rewrite_query_safe(
            client,
            question,
            model_name=rewrite_model_name,
        )
    else:
        plan = fallback_rewrite(question)

    queries = [plan.rewritten_query]
    queries.extend(
        query
        for query in plan.sub_queries
        if query
    )

    all_results = []

    for query in queries:
        try:
            all_results.append(
                retriever.retrieve(query, top_k=top_k)
            )
        except Exception:
            continue

    return merge_retrieval_results(all_results, top_k)