from functools import lru_cache

import tiktoken

ENCODING_NAME = "cl100k_base"
TOKENS_PER_MESSAGE = 3
TOKENS_PER_NAME = 1


@lru_cache(maxsize=1)
def get_encoding():
    return tiktoken.get_encoding(ENCODING_NAME)


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(get_encoding().encode(text))


def count_message_tokens(message: dict) -> int:
    total = TOKENS_PER_MESSAGE

    content = message.get("content")
    if isinstance(content, str):
        total += count_tokens(content)

    name = message.get("name")
    if isinstance(name, str):
        total += TOKENS_PER_NAME + count_tokens(name)

    tool_calls = message.get("tool_calls")
    for tool_call in tool_calls or []:
        function = tool_call.get("function", {})
        total += count_tokens(function.get("name", ""))
        total += count_tokens(function.get("arguments", ""))

    return total


def count_messages_tokens(messages: list[dict]) -> int:
    return sum(count_message_tokens(message) for message in messages)


def group_messages(messages: list[dict]) -> list[list[dict]]:
    groups = []
    current = []

    for message in messages:
        role = message.get("role")

        if role == "system":
            if current:
                groups.append(current)
                current = []
            groups.append([message])
            continue

        if role == "user":
            if current:
                groups.append(current)
            current = [message]
            continue
    
        if role == "tool":
            if current:
                current.append(message)
            else:
                current = [message]
            continue

        if role == "assistant":
            has_tool_calls = bool(message.get("tool_calls"))
            after_tool_results = bool(current and current[-1].get("role") == "tool")

            if has_tool_calls or after_tool_results:
                if current:
                    groups.append(current)
                current = [message]
            else:
                current.append(message)
            continue
    
        current.append(message)

    if current:
        groups.append(current)

    return groups


class ContextBudget:
    def __init__(
        self,
        max_tokens: int = 12000,
        reserved_output_tokens: int = 1500,
        token_counter=count_messages_tokens,
    ):
        if reserved_output_tokens < 0:
            raise ValueError("reserved_output_tokens 不能小于 0")
        if reserved_output_tokens >= max_tokens:
            raise ValueError("reserved_output_tokens 必须小于 max_tokens")

        self.max_tokens = max_tokens
        self.reserved_output_tokens = reserved_output_tokens
        self.token_counter = token_counter
        self.prompt_limit = max_tokens - reserved_output_tokens

    def usage(self, messages: list[dict]) -> int:
        return self.token_counter(messages)

    def fits(self, messages: list[dict]) -> bool:
        return self.usage(messages) <= self.prompt_limit

    def fit_messages(self, messages: list[dict]) -> list[dict]:
        groups = group_messages(messages)
        system_groups = [g for g in groups if g[0].get("role") == "system"]
        other_groups = [g for g in groups if g[0].get("role") != "system"]

        for start in range(len(other_groups) + 1):
            candidate = [
                message
                for group in system_groups + other_groups[start:]
                for message in group
            ]
            if self.fits(candidate):
                return candidate

        raise ValueError("只保留系统消息仍然超过上下文预算")