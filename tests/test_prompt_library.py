import pytest

from app.models import JobDescription
from app.prompt_library import (
    PromptLibrary,
    PromptLibraryError,
    PromptTemplate,
)
from app.prompts import (
    PROMPT_LIBRARY,
    build_analysis_messages,
    build_chat_messages,
    build_jd_parse_messages,
)


def make_library():
    library = PromptLibrary()
    library.register(
        PromptTemplate(
            name="greeting",
            version="v1",
            content="你好，{name}",
            description="问候模板",
        )
    )
    return library


def test_render_replaces_variables():
    library = make_library()

    assert library.render("greeting", name="Codex") == "你好，Codex"


def test_render_raises_when_variable_missing():
    library = make_library()

    with pytest.raises(PromptLibraryError, match="缺少变量"):
        library.render("greeting")


def test_get_unknown_template_raises():
    library = make_library()

    with pytest.raises(PromptLibraryError, match="未知 Prompt"):
        library.render("not-exist")


def test_duplicate_registration_raises():
    library = make_library()

    with pytest.raises(PromptLibraryError, match="已存在"):
        library.register(
            PromptTemplate(name="greeting", version="v1", content="重复")
        )


def test_prompt_library_has_day30_templates():
    assert PROMPT_LIBRARY.get("jd_parse_system").version == "v1"
    assert PROMPT_LIBRARY.get("analysis_system").version == "v1"
    assert PROMPT_LIBRARY.get("analysis_user").version == "v1"
    assert PROMPT_LIBRARY.get("chat_system").version == "v1"
    assert PROMPT_LIBRARY.get("chat_user").version == "v1"


def test_build_jd_parse_messages_uses_library():
    messages = build_jd_parse_messages("测试 JD")

    assert messages[0]["role"] == "system"
    assert "示例" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "测试 JD"}


def test_build_analysis_messages_uses_library():
    job = JobDescription(
        company="测试公司",
        title="AI Agent 工程师",
        seniority="mid",
        responsibilities=["设计 Agent"],
        requirements=["Python"],
        keywords=["Agent"],
        domain="AI 应用",
    )

    messages = build_analysis_messages(job, "RAG 上下文")

    assert "先完成以下思考" in messages[0]["content"]
    assert "RAG 上下文" in messages[1]["content"]


def test_build_chat_messages_uses_library():
    messages = build_chat_messages(
        [{"role": "user", "content": "旧问题"}],
        "知识库上下文",
        "当前问题",
    )

    assert messages[0]["role"] == "system"
    assert "知识库上下文" in messages[2]["content"]
    assert "当前问题" in messages[2]["content"]