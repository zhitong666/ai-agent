# 这里要 mock 掉 session_store、检索器和 DeepSeek 调用
# 两个测试分别验证什么：
# 1. answer_question 返回模型内容，并把本轮 user/assistant 消息追加进对应 session 的 memory。
# 2. 当 memory 里已经有历史消息时，这些历史消息真的被传进了 client.chat.completions.create 的 messages 参数。这是“记忆”最关键的一步，否则模型还是不知道上一轮。
# 一个容易踩的坑：这里 patch 的是 "app.agent.session_store"，不是 "app.memory.session_store"。因为 agent.py 里写的是 from app.memory import session_store，所以 agent 模块里已经有自己的 session_store 名字，patch 要指向它。

from unittest.mock import MagicMock, patch

from app import agent
from app.memory import SessionStore


class FakeRetriever:
    def retrieve(self, query, top_k=3):
        return [
            {
                "doc": {
                    "chunk_id": "doc-rag-0",
                    "doc_id": "doc-rag",
                    "title": "RAG",
                    "text": "RAG 通过 Embedding 和向量检索找到相关资料。",
                },
                "score": 0.9,
            }
        ]

# build_sources 能把一条检索结果转成一个 Source，并正确带出 chunk_id、title、score

def test_build_sources_returns_source_list():
    results = [
        {
            "doc": {
                "chunk_id": "doc-rag-0",
                "doc_id": "doc-rag",
                "title": "RAG",
                "text": "RAG 通过 Embedding 和向量检索找到相关资料。",
            },
            "score": 0.9,
        }
    ]

    sources = agent.build_sources(results)

    assert len(sources) == 1
    assert sources[0].chunk_id == "doc-rag-0"
    assert sources[0].title == "RAG"
    assert sources[0].score == 0.9


# answer_question 返回 ChatResponse，其中 reply 和 sources 都正确，同时消息仍被追加进 memory
def test_answer_question_returns_reply_and_sources():
    store = SessionStore()

    message = MagicMock()
    message.content = "RAG 是检索增强生成。"

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]

    with patch("app.agent.session_store", store), patch.object(
        agent.client.chat.completions,
        "create",
        return_value=response,
    ):
        result = agent.answer_question("s1", "什么是 RAG", retriever=FakeRetriever())

    assert result.reply == "RAG 是检索增强生成。"
    assert len(result.sources) == 1
    assert result.sources[0].chunk_id == "doc-rag-0"

    assert store.get("s1").get_messages() == [
        {"role": "user", "content": "什么是 RAG"},
        {"role": "assistant", "content": "RAG 是检索增强生成。"},
    ]


# 历史消息仍然被传进 messages，保证 Day 11 的记忆能力没有因为 Day 12 改动而退化
def test_answer_question_includes_history_in_messages():
    store = SessionStore()
    store.get("s1").add("user", "上一轮问题")
    store.get("s1").add("assistant", "上一轮回答")

    message = MagicMock()
    message.content = "本轮回答"

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]

    with patch("app.agent.session_store", store), patch.object(
        agent.client.chat.completions,
        "create",
        return_value=response,
    ) as mock_create:
        agent.answer_question("s1", "当前问题", retriever=FakeRetriever())

    messages_passed = mock_create.call_args.kwargs["messages"]
    contents = [m["content"] for m in messages_passed]

    assert any("上一轮问题" in content for content in contents)
    assert any("上一轮回答" in content for content in contents)