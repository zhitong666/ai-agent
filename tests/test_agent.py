from unittest.mock import MagicMock, patch

from app import agent
from app.models import JobDescription

class FakeRetriever:
    def retrieve(self, query: str, top_k: int = 3):
        return [
            {
                "doc": {
                    "id": "doc-rag",
                    "title": "RAG",
                    "text": "RAG 通过 Embedding 和向量检索找到相关资料。",
                },
                "score": 0.9,
            }
        ]

def test_analyze_job():
    fake_job = JobDescription(
        company="字节跳动",
        title="AI Agent 工程师",
        seniority="mid",
        responsibilities=["设计 Agent"],
        requirements=["Python", "RAG"],
        keywords=["Agent", "RAG"],
        domain="AI 应用",
    )

    tool_call = MagicMock()
    tool_call.function.arguments = (
        '{"summary":"AI Agent 岗位",'
        '"matched_skills":["Python"],'
        '"missing_skills":["Docker"],'
        '"interview_questions":["解释 function calling"],'
        '"study_plan":["学习 RAG"]}'
    )

    message = MagicMock()
    message.tool_calls = [tool_call]

    choice = MagicMock()
    choice.message = message
    
    response = MagicMock()
    response.choices = [choice]

    with patch("app.agent.parse_job_description", return_value=fake_job), patch.object(
        agent.client.chat.completions,
        "create",
        return_value=response,
    ):
        result = agent.analyze_job("某 JD", retriever=FakeRetriever())

    assert result.summary == "AI Agent 岗位"
    assert result.matched_skills == ["Python"]
    assert result.missing_skills == ["Docker"]

    