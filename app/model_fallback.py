from app.config import get_settings


def parse_model_csv(raw: str | None) -> list[str]:
    if not raw:
        return []

    return [
        item.strip()
        for item in raw.split(",")
        if item.strip()
    ]


def get_fallback_models(primary_model: str) -> list[str]:
    settings = get_settings()
    models = parse_model_csv(settings.llm_fallback_models_csv)

    return [
        model
        for model in models
        if model != primary_model
    ]