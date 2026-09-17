import re
from dataclasses import dataclass
from typing import Any

DEFAULT_MAX_INPUT_LENGTH = 2000

INJECTION_MARKERS = (
    "ignore previous instructions",
    "忽略之前指令",
    "忽略上述指令",
    "忘记之前的规则",
    "system prompt",
    "<|im_start|>",
    "<|im_end|>",
)

INJECTION_PATTERNS = (
    re.compile(r"system\s*:", re.IGNORECASE),
    re.compile(r"role\s*:\s*system", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"\[system\]", re.IGNORECASE),
)

_CONTROL_CHARS = {chr(i) for i in range(32)} - {"\n", "\t"}


@dataclass(frozen=True)
class InputGuardResult:
    safe: bool
    text: str
    reason: str = ""


@dataclass(frozen=True)
class ToolArgumentsGuardResult:
    safe: bool
    arguments: dict
    reason: str = ""


def contains_prompt_injection_pattern(text: str) -> bool:
    normalized = text.lower()

    if any(marker in normalized for marker in INJECTION_MARKERS):
        return True

    return any(pattern.search(text) for pattern in INJECTION_PATTERNS)


def sanitize_text(text: str) -> str:
    cleaned = "".join(
        char
        for char in text
        if char not in _CONTROL_CHARS
    )

    return cleaned.strip()


# 做清洗、长度限制、注入检测
def guard_user_input(
    text: str,
    max_length: int = DEFAULT_MAX_INPUT_LENGTH,
) -> InputGuardResult:
    if not isinstance(text, str):
        return InputGuardResult(False, "", "input must be a string")

    sanitized = sanitize_text(text)

    if not sanitized:
        return InputGuardResult(False, "", "input is empty")

    if len(sanitized) > max_length:
        return InputGuardResult(
            False,
            "",
            f"input exceeds {max_length} characters",
        )

    if contains_prompt_injection_pattern(sanitized):
        return InputGuardResult(
            False,
            "",
            "input contains prompt injection",
        )

    return InputGuardResult(True, sanitized)


def _sanitize_value(
    value: Any,
    path: str,
    max_length: int,
):
    if isinstance(value, str):
        result = guard_user_input(value, max_length)

        if not result.safe:
            return False, None, f"{path}: {result.reason}"

        return True, result.text, ""

    if isinstance(value, dict):
        sanitized = {}

        for key, nested_value in value.items():
            ok, clean_value, reason = _sanitize_value(
                nested_value,
                f"{path}.{key}",
                max_length,
            )

            if not ok:
                return False, None, reason

            sanitized[key] = clean_value

        return True, sanitized, ""

    if isinstance(value, list):
        sanitized = []

        for index, nested_value in enumerate(value):
            ok, clean_value, reason = _sanitize_value(
                nested_value,
                f"{path}[{index}]",
                max_length,
            )

            if not ok:
                return False, None, reason

            sanitized.append(clean_value)

        return True, sanitized, ""

    if value is None or isinstance(value, (int, float, bool)):
        return True, value, ""

    return False, None, f"{path}: unsupported value type"


# 递归处理字符串、dict、list
def guard_tool_arguments(
    tool_name: str,
    arguments: dict,
    max_length: int = DEFAULT_MAX_INPUT_LENGTH,
) -> ToolArgumentsGuardResult:
    if not isinstance(arguments, dict):
        return ToolArgumentsGuardResult(
            False,
            {},
            "arguments must be an object",
        )

    sanitized: dict = {}

    for key, value in arguments.items():
        if not isinstance(key, str):
            return ToolArgumentsGuardResult(
                False,
                {},
                f"{tool_name}: argument key must be a string",
            )

        key_result = guard_user_input(key, max_length)

        if not key_result.safe:
            return ToolArgumentsGuardResult(
                False,
                {},
                f"{tool_name}.{key}: {key_result.reason}",
            )

        ok, clean_value, reason = _sanitize_value(
            value,
            f"{tool_name}.{key}",
            max_length,
        )

        if not ok:
            return ToolArgumentsGuardResult(False, {}, reason)

        sanitized[key_result.text] = clean_value

    return ToolArgumentsGuardResult(True, sanitized)