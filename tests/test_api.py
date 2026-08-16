from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models import JobDescription

client = TestClient(app)

def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_parse_jd_returns_job_description():
    fake_job = JobDescription(
        company="测试公司",
        title="AI Agent 工程师",
        seniority="mid",
        responsibilities=["设计 Agent"],
        requirements=["Python"],
        keywords=["Agent"],
        domain="AI 应用",
    )

    with patch("app.main.parse_job_description", return_value=fake_job):
        response = client.post(
            "/jd/parse",
            json={"text": "某公司 AI Agent 工程师 JD"}
        )

    assert response.status_code == 200
    assert response.json()["company"] == "测试公司"
    assert response.json()["title"] == "AI Agent 工程师"

def test_parse_jd_rejects_empty_text():
    response = client.post("/jd/parse", json={"text": ""})

    assert response.status_code == 422