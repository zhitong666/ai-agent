from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_parse_jd_returns_job_description():
    response = client.post(
        "/jd/parse",
        json={"text": "某公司 AI Agent 工程师 JD"},
    )

    assert response.status_code == 200
    assert response.json()["company"] == "示例公司"
    assert response.json()["title"] == "AI Agent 工程师"

def test_parse_jd_rejects_empty_text():
    response = client.post("/jd/parse", json={"text": ""})

    assert response.status_code == 422