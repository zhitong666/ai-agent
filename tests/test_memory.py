# 这两个测试验证什么：
# 1. add 能按顺序追加消息，get_messages 能完整返回。
# 2. 同一个 session_id 拿到的是同一个 Memory 对象，不同 id 是不同的对象。is 是判断“是不是同一个对象”，不是判断内容是否相等。

from app.memory import Memory, SessionStore

def test_memory_adds_and_returns_messages():
    memory = Memory()

    memory.add("user", "你好")
    memory.add("assistant", "你好，有什么可以帮你")

    messages = memory.get_messages()

    assert messages == [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好，有什么可以帮你"},
    ]


def test_session_store_returns_same_memory_for_same_id():
    store = SessionStore()

    first = store.get("s1")
    second = store.get("s1")
    other = store.get("s2")

    assert first is second
    assert first is not other