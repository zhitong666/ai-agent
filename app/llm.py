import os
from functools import lru_cache

from dotenv import load_dotenv
from openai import OpenAI

from app.models import JobDescription
from app.prompts import build_jd_parse_messages
from app.structured_output import (
    build_tool_parameters_from_model,
)
from app.function_calling import call_required_function
from app.model_registry import get_model_name


load_dotenv()


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required to create the OpenAI client"
        )

    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL"),
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
        model_name=get_model_name("jd_parse", os.getenv("OPENAI_MODEL")),
        max_attempts=3,
    )