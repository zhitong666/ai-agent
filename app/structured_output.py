import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)


class StructuredOutputError(ValueError):
    """模型结构化输出无法解析或校验时抛出。"""



# 处理模型偶尔把 JSON 包在 Markdown 代码块里的情况
def _strip_code_fences(raw: str) -> str:
    text = raw.strip()

    if not text.startswith("```"):
        return text
    
    lines = text.splitlines()

    if lines and lines[0].startswith("```"):
        lines = lines[1:]

    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines).strip()


# 把 json.JSONDecodeError 转成统一的 StructuredOutputError
def parse_json_object(raw: str) -> dict:
    if not isinstance(raw, str):
        raise StructuredOutputError(
            f"模型返回的不是字符串: {type(raw).__name__}"
        )

    try:
        data = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(
            f"模型返回的 JSON 无法解析: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise StructuredOutputError(
            f"模型返回的 JSON 顶层必须是对象，实际是 {type(data).__name__}"
        )

    return data


# 把 Pydantic 的 ValidationError 也转成统一错误
def validate_model(data: dict, model: type[ModelT]) -> ModelT:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise StructuredOutputError(f"Pydantic 校验失败: {exc}") from exc


def parse_and_validate(raw: str, model: type[ModelT]) -> ModelT:
    return validate_model(parse_json_object(raw), model)


# 使用 model_json_schema()，让工具参数和 Pydantic 模型保持同一个数据源
def build_tool_parameters_from_model(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
    }