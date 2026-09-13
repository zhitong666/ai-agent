import pytest

from app.context import (
    ContextBudget,
    count_message_tokens,
    count_messages_tokens,
    count_tokens,
    group_messages,
)


def fake_counter(messages):
    return sum(len(message.get("content", "")) for message in messages)


# 验证真实 token 计数和固定消息开销
def test_count_tokens_handles_empty_text():
    assert count_tokens("") == 0


# 验证真实 token 计数和固定消息开销
def test_count_tokens_counts_english_words():
    assert count_tokens("hello") == 1
    assert count_tokens("hello world") == 2


# 验证真实 token 计数和固定消息开销
def test_count_message_tokens_adds_fixed_overhead():
    message = {"role": "user", "content": "hello"}

    assert count_message_tokens(message) == 3 + count_tokens("hello")


# 验证真实 token 计数和固定消息开销
def test_count_messages_tokens_sums_all_messages():
    messages = [
        {"role": "system", "content": "you"},
        {"role": "user", "content": "hello"},
    ]

    assert count_messages_tokens(messages) == (
        3 + count_tokens("you") + 3 + count_tokens("hello")
    )


def test_group_messages_groups_chat_turns():
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
    ]

    assert group_messages(messages) == [
        [messages[0]],
        [messages[1], messages[2]],
        [messages[3], messages[4]],
    ]


def test_group_messages_keeps_tool_calls_with_tool_results():
    messages = [
        {"role": "user", "content": "q"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"function": {"name": "search_knowledge", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "result"},
        {"role": "assistant", "content": "answer"},
    ]

    assert group_messages(messages) == [
        [messages[0]],
        [messages[1], messages[2]],
        [messages[3]],
    ]


def test_fit_messages_drops_oldest_turns():
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
    ]

    budget = ContextBudget(
        max_tokens=12,
        reserved_output_tokens=5,
        token_counter=fake_counter,
    )

    fitted = budget.fit_messages(messages)

    assert [message["content"] for message in fitted] == ["SYS", "q2", "a2"]


def test_fit_messages_keeps_all_when_within_budget():
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "hello"},
    ]

    budget = ContextBudget(
        max_tokens=20,
        reserved_output_tokens=5,
        token_counter=fake_counter,
    )

    assert budget.fit_messages(messages) == messages


def test_fit_messages_raises_when_system_too_large():
    budget = ContextBudget(
        max_tokens=5,
        reserved_output_tokens=0,
        token_counter=fake_counter,
    )

    with pytest.raises(ValueError, match="系统消息"):
        budget.fit_messages(
            [
                {"role": "system", "content": "SYSTEM"},
                {"role": "user", "content": "hello"},
            ]
        )