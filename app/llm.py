import os

from dotenv import load_dotenv
from openai import OpenAI

from app.models import JobDescription
from app.prompts import build_jd_parse_messages
from app.structured_output import (
    build_tool_parameters_from_model,
)
from app.function_calling import call_required_function


load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

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
        model_name=os.environ["OPENAI_MODEL"],
        max_attempts=3,
    )
    
