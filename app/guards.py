PROMPT_INJECTION_MARKERS = (
    "忽略之前指令",
    "ignore previous instructions",
    "system:",
    "system prompt",
    "忘记之前的规则",
)


def contains_prompt_injection(text: str) -> bool:
    # 用 lower() 统一转小写，避免大小写绕过
    normalized = text.lower()
    # any(...) 表示只要命中任意一个关键词就返回 True
    return any(marker.lower() in normalized for marker in PROMPT_INJECTION_MARKERS)


def validate_final_answer(answer: str) -> str:
    cleaned = answer.strip()

    if not cleaned:
        return "抱歉，我没有生成有效答案。"

    if contains_prompt_injection(cleaned):
        return "抱歉，答案包含不安全内容，已被拦截。"

    return cleaned


# 返回 None 表示参数合法；返回字符串表示参数不合法
def validate_tool_arguments(tool_name: str, arguments: dict) -> str | None:
    # apply_job 是当前唯一的危险工具，所以这里先只校验它
    if tool_name != "apply_job":
        return None

    company = arguments.get("company", "").strip()
    position = arguments.get("position", "").strip()

    if not company or not position:
        return "company 和 position 不能为空"

    if contains_prompt_injection(company) or contains_prompt_injection(position):
        return "参数包含可疑指令"

    return None
