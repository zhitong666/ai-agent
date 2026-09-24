from app.prompts import build_chat_messages


def system_content(messages):
    return messages[0]["content"]


def test_general_scene_uses_general_prompt():
    messages = build_chat_messages(
        [],
        "",
        "什么是 RAG？",
        scene="general",
    )

    assert "通用 AI 助手" in system_content(messages)
    assert "什么是 RAG？" in messages[-1]["content"]


def test_interview_scene_uses_interview_prompt():
    messages = build_chat_messages(
        [],
        "",
        "开始面试",
        scene="interview",
    )

    assert "技术面试官" in system_content(messages)


def test_resume_scene_uses_resume_prompt():
    messages = build_chat_messages(
        [],
        "",
        "帮我诊断简历",
        scene="resume",
    )

    assert "简历" in system_content(messages)


def test_project_scene_uses_knowledge_context():
    messages = build_chat_messages(
        [],
        "[doc-1] FastAPI 基础",
        "FastAPI 需要掌握什么",
        scene="project",
    )

    assert "知识库助手" in system_content(messages)
    assert "[doc-1]" in messages[-1]["content"]