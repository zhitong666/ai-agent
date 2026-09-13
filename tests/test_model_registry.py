import pytest

from app.model_registry import (
    ModelRegistryError,
    estimate_cost,
    get_model_name,
    get_model_profile,
    select_model,
)


def test_select_model_returns_structured_model_for_jd_parse():
    assert select_model("jd_parse") == "deepseek-chat"


def test_select_model_prefers_reasoner_for_job_analysis():
    assert select_model("job_analysis") == "deepseek-reasoner"


def test_select_model_returns_chat_model_for_chat():
    assert select_model("chat") == "deepseek-chat"


def test_select_model_returns_agent_model_for_agent():
    assert select_model("agent") == "deepseek-chat"


def test_get_model_name_uses_override():
    assert get_model_name("jd_parse", "custom-model") == "custom-model"


def test_get_model_profile_returns_profile():
    profile = get_model_profile("deepseek-chat")

    assert profile.provider == "DeepSeek"
    assert profile.supports_tools is True
    assert profile.context_window == 64000


def test_estimate_cost_calculates_million_token_cost():
    assert estimate_cost("deepseek-chat", 1_000_000, 0) == 0.27
    assert estimate_cost("deepseek-chat", 0, 1_000_000) == 1.10


def test_estimate_cost_raises_for_unknown_model():
    with pytest.raises(ModelRegistryError, match="未知模型"):
        estimate_cost("not-exist", 100, 100)


def test_select_model_raises_for_unknown_task():
    with pytest.raises(ModelRegistryError, match="未知任务"):
        select_model("not-exist")