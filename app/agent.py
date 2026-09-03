import json 
import os
from functools import lru_cache
from pathlib import Path

from app.llm import client, parse_job_description
from app.models import JobAnalysis
from app.rag import build_retriever

from app.memory import session_store

ANALYSIS_SYSTEM_PROMPT = """你是 AI 岗位分析师。
根据岗位信息与知识库检索结果，生成岗位分析。
必须调用 save_job_analysis 工具。"""

ANALYSIS_TOOL = {
    "type": "function",
    "function": {
        "name": "save_job_analysis",
        "description": "保存岗位分析结果",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string"},
                "matched_skills": {"type": "array", "items": {"type": "string"}},
                "missing_skills": {"type": "array", "items": {"type": "string"}},
                "interview_questions": {"type": "array", "items": {"type": "string"}},
                "study_plan": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "summary",
                "matched_skills",
                "missing_skills",
                "interview_questions",
                "study_plan",
            ],
        },
    },
}

@lru_cache(maxsize=1)
def get_retriever():
    return build_retriever(Path("data/knowledge_base.json"))

def format_context(results: list[dict]) -> str:
    lines = []

    for item in results:
        doc = item["doc"]
        score = item["score"]
        chunk_id = doc.get("chunk_id", doc.get("id", "unknown"))
        lines.append(f"[{chunk_id}] {doc['title']}: {doc['text']} (score={score:.3f})")

    return "\n".join(lines)

def generate_analysis(job, context: str) -> JobAnalysis:
    user_content = f"岗位信息：\n{job.model_dump_json()}\n\n知识库：\n{context}"

    response = client.chat.completions.create(
        model=os.environ["OPENAI_MODEL"],
        messages=[
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        tools=[ANALYSIS_TOOL],
        tool_choice={
            "type": "function",
            "function": {"name": "save_job_analysis"},
        },
    )

    message = response.choices[0].message

    if not message.tool_calls:
        raise RuntimeError("模型没有返回 tool_calls")

    arguments = json.loads(message.tool_calls[0].function.arguments)
    return JobAnalysis.model_validate(arguments)

# 多步流程的入口
def analyze_job(jd_text: str, retriever=None) -> JobAnalysis:
    job = parse_job_description(jd_text)

    retriever = retriever or get_retriever() 

    query = " ".join(job.keywords) if job.keywords else job.title

    results = retriever.retrieve(query, top_k=3) # 检索相关知识

    context = format_context(results) # 把检索结果拼成文本

    return generate_analysis(job, context) # 调用 DeepSeek 生成分析


CHAT_SYSTEM_PROMPT = """你是 AI 岗位咨询助手。
根据知识库和对话历史回答用户问题，回答要简洁、准确。
如果知识库没有相关内容，就明确说明不知道。"""

# 当前问题会带上刚检索到的知识上下文。
# 这里没有用 function calling，而是让模型直接返回文本，因为聊天场景需要自然多轮回答。
# 调用结束后，把本轮用户问题和模型回答追加进 memory，下一轮就能看到

def answer_question(session_id: str, question: str, retriever=None) -> str:
    memory = session_store.get(session_id)
    retriever = retriever or get_retriever()

    results = retriever.retrieve(question, top_k=3)
    context = format_context(results)

    # *memory.get_messages() 把历史消息展开，放进当前 messages 列表
    messages = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        *memory.get_messages(),
        {"role": "user", "content": f"知识库：\n{context}\n\n问题：{question}"},
    ]

    response = client.chat.completions.create(
        model=os.environ["OPENAI_MODEL"],
        messages=messages,
    )
    reply = response.choices[0].message.content

    memory.add("user", question)
    memory.add("assistant", reply)

    return reply
