from functools import lru_cache

from openai import OpenAI

from app.config import get_settings
from app.function_calling import call_required_function
from app.model_registry import get_model_name
from app.models import JobDescription
from app.prompts import build_jd_parse_messages
from app.structured_output import (
    build_tool_parameters_from_model,
)


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    settings = get_settings()
    api_key = settings.openai_api_key.get_secret_value()

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required to create the OpenAI client"
        )

    return OpenAI(
        api_key=api_key,
        base_url=settings.openai_base_url,
    )


class _LazyOpenAI:
    def __getattr__(self, name: str):
        return getattr(get_client(), name)


client = _LazyOpenAI()


SAVE_JOB_DESCRIPTION_TOOL = {
    "type": "function",
    "function": {
        "name": "save_job_description",
        "description": "保存解析后的岗位信息",
        "parameters": build_tool_parameters_from_model(JobDescription),
    },
}


def parse_job_description(jd_text: str) -> JobDescription:
    return call_required_function(
        client,
        build_jd_parse_messages(jd_text),
        [SAVE_JOB_DESCRIPTION_TOOL],
        "save_job_description",
        JobDescription,
        model_name=get_model_name(
            "jd_parse",
            get_settings().openai_model,
        ),
        max_attempts=3,
    )