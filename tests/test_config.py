import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def set_required_secrets(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)


def test_settings_requires_secrets(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_reads_secrets_as_secret_str(monkeypatch) -> None:
    set_required_secrets(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.openai_api_key.get_secret_value() == "sk-test"
    assert settings.jwt_secret.get_secret_value() == "x" * 32
    assert "sk-test" not in repr(settings)


def test_settings_rejects_unknown_environment(monkeypatch) -> None:
    set_required_secrets(monkeypatch)
    monkeypatch.setenv("APP_ENV", "invalid")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_validates_llm_concurrency(monkeypatch) -> None:
    set_required_secrets(monkeypatch)
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "0")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_validates_jwt_secret_length(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JWT_SECRET", "short")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_caches_result(monkeypatch) -> None:
    set_required_secrets(monkeypatch)

    first = get_settings()
    second = get_settings()

    assert first is second