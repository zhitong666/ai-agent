from unittest.mock import MagicMock, patch

from app import llm

def test_parse_job_description():
    fake_choice = MagicMock()
    fake_choice.message.content = (
        '{"company":"字节跳动",'
        '"title":"AI Agent 工程师",'
        '"seniority":"mid",'
        '"responsibilities":[],'
        '"requirements":["Python"],'
        '"keywords":["Agent"],'
        '"domain":""}'
    )

    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    with patch.object(
        llm.client.chat.completions,
        "create",
        return_value=fake_response,
    ):
        result = llm.parse_job_description("某 JD 文本")

    assert result.company == "字节跳动"
    assert result.title == "AI Agent 工程师"