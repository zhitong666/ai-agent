from app.models import JobDescription
from app.prompts import (
    build_analysis_messages,
    build_chat_messages,
    build_jd_parse_messages,
)


def test_build_jd_parse_messages_contains_few_shot_example():
    messages = build_jd_parse_messages("测试 JD 文本")

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "示例" in messages[0]["content"]
    assert "字节跳动" in messages[0]["content"]
    assert "AI Agent 工程师" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "测试 JD 文本"}


def test_build_analysis_messages_includes_cot_instruction():
    job = JobDescription(
        company="测试公司",
        title="AI Agent 工程师",
        seniority="mid",
        responsibilities=["设计 Agent"],
        requirements=["Python", "RAG"],
        keywords=["Agent", "RAG"],
        domain="AI 应用",
    )

    messages = build_analysis_messages(job, "RAG 相关知识库上下文")

    system = messages[0]["content"]
    user = messages[1]["content"]

    assert "先完成以下思考" in system
    assert "岗位信息" in user
    assert "RAG 相关知识库上下文" in user


def test_build_analysis_messages_can_disable_cot():
    job = JobDescription(
        company="测试公司",
        title="AI Agent 工程师",
        seniority="mid",
        responsibilities=[],
        requirements=[],
        keywords=[],
        domain="",
    )

    messages = build_analysis_messages(job, "上下文", cot=False)

    assert "先完成以下思考" not in messages[0]["content"]


def test_build_chat_messages_keeps_history_and_current_question():
    history = [
        {"role": "user", "content": "上一轮问题"},
        {"role": "assistant", "content": "上一轮回答"},
    ]

    messages = build_chat_messages(
        history,
        "知识库上下文",
        "当前问题",
    )

    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "上一轮问题"}
    assert messages[2] == {"role": "assistant", "content": "上一轮回答"}
    assert messages[3]["role"] == "user"
    assert "知识库上下文" in messages[3]["content"]
    assert "当前问题" in messages[3]["content"]