import pytest

from app.models import JobDescription
from app.structured_output import (
    StructuredOutputError,
    build_tool_parameters_from_model,
    parse_and_validate,
    parse_json_object,
)


def test_parse_json_object_returns_dict():
    raw = '{"company":"测试公司","title":"AI 工程师"}'

    data = parse_json_object(raw)

    assert data == {"company": "测试公司", "title": "AI 工程师"}


def test_parse_json_object_strips_markdown_code_fence():
    raw = '```json\n{"company":"测试公司","title":"AI 工程师"}\n```'

    data = parse_json_object(raw)

    assert data["company"] == "测试公司"
    assert data["title"] == "AI 工程师"


def test_parse_json_object_raises_on_invalid_json():
    with pytest.raises(StructuredOutputError, match="JSON 无法解析"):
        parse_json_object("{not valid json")


def test_parse_json_object_raises_on_non_object_root():
    with pytest.raises(StructuredOutputError, match="顶层必须是对象"):
        parse_json_object('["a", "b"]')


def test_parse_and_validate_returns_model():
    raw = (
        '{"company":"测试公司",'
        '"title":"AI 工程师",'
        '"seniority":"mid"}'
    )

    job = parse_and_validate(raw, JobDescription)

    assert job.company == "测试公司"
    assert job.title == "AI 工程师"
    assert job.seniority == "mid"
    assert job.responsibilities == []


def test_parse_and_validate_raises_when_required_field_missing():
    with pytest.raises(StructuredOutputError, match="Pydantic 校验失败"):
        parse_and_validate('{"company":"测试公司"}', JobDescription)


def test_parse_and_validate_raises_on_invalid_enum():
    raw = (
        '{"company":"测试公司",'
        '"title":"AI 工程师",'
        '"seniority":"manager"}'
    )

    with pytest.raises(StructuredOutputError, match="Pydantic 校验失败"):
        parse_and_validate(raw, JobDescription)


def test_build_tool_parameters_from_model_uses_json_schema():
    parameters = build_tool_parameters_from_model(JobDescription)

    assert parameters["type"] == "object"
    assert parameters["additionalProperties"] is False
    assert set(parameters["required"]) == {"company", "title"}
    assert "company" in parameters["properties"]
    assert "seniority" in parameters["properties"]
    assert "junior" in parameters["properties"]["seniority"]["enum"]