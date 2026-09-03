# 这个模块专门管理会话记忆，和检索、LLM 解耦

# Memory 保存一个会话的消息列表
class Memory:
    def __init__(self):
        self.messages = []

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def get_messages(self) -> list[dict]:
        return list(self.messages)

    def clear(self) -> None:
        self.messages.clear()


# SessionStore 用 session_id 作为 key，管理多个会话
class SessionStore:
    def __init__(self):
        self.sessions = {}

    def get(self, session_id: str) -> Memory:
        if session_id not in self.sessions:
            self.sessions[session_id] = Memory()
        return self.sessions[session_id]


# session_store 是模块级单例，服务运行期间一直存在，所以能记住不同 session
session_store = SessionStore()

