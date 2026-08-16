import pytest

from app.day1 import parse_text

def test_parse_text():
  assert parse_text("字节跳动 | AI Agent 工程师") == {
    "company": "字节跳动",
    "title": "AI Agent 工程师",
  }

def test_empty_text_raises():
    with pytest.raises(ValueError):
        parse_text("")
