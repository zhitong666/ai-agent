import pytest

from app.embedding_registry import (
    EmbeddingRegistryError,
    get_embedding_model_name,
    get_embedding_profile,
    select_embedding_model,
)


def test_select_embedding_model_returns_bge_small_for_chinese():
    assert select_embedding_model("rag_chinese") == "BAAI/bge-small-zh-v1.5"


def test_select_embedding_model_returns_bge_m3_for_multilingual():
    assert select_embedding_model("rag_multilingual") == "BAAI/bge-m3"


def test_select_embedding_model_returns_low_dimension_model_for_low_latency():
    assert (
        select_embedding_model("rag_low_latency")
        == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )


def test_select_embedding_model_returns_long_context_model():
    assert select_embedding_model("rag_long_documents") == "BAAI/bge-m3"


def test_get_embedding_model_name_uses_override():
    assert get_embedding_model_name("rag_chinese", "custom-model") == "custom-model"


def test_get_embedding_profile_returns_dimension():
    profile = get_embedding_profile("BAAI/bge-m3")

    assert profile.dimension == 1024
    assert profile.supports_multilingual is True
    assert profile.max_sequence_length == 8192


def test_select_embedding_model_raises_for_unknown_scenario():
    with pytest.raises(EmbeddingRegistryError, match="未知 Embedding 场景"):
        select_embedding_model("not-exist")


def test_get_embedding_profile_raises_for_unknown_model():
    with pytest.raises(EmbeddingRegistryError, match="未知 Embedding 模型"):
        get_embedding_profile("not-exist")