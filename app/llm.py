import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from app.models import JobDescription
from app.prompts import build_jd_parse_messages

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
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "company": {"type": "string"},
                "title": {"type": "string"},
                "seniority": {
                    "type": "string",
                    "enum": ["junior", "mid", "senior", "staff", "unknown"],
                },
                "responsibilities": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "domain": {"type": "string"},
            },
            "required": [
                "company",
                "title",
                "seniority",
                "responsibilities",
                "requirements",
                "keywords",
            ],
        },
    },
}

def parse_job_description(jd_text: str) -> JobDescription:
    # `client.chat.completions.create()` 发起一次对话补全请求
    response = client.chat.completions.create( 
        model=os.environ["OPENAI_MODEL"],
        messages=build_jd_parse_messages(jd_text),
        tools=[SAVE_JOB_DESCRIPTION_TOOL],
        tool_choice={
            "type": "function",
            "function": {"name": "save_job_description"},
        },
    )

    message = response.choices[0].message

    if not message.tool_calls:
        raise RuntimeError("模型没有返回 tool_calls")

    tool_call = message.tool_calls[0]
    arguments = json.loads(tool_call.function.arguments)
    return JobDescription.model_validate(arguments)
