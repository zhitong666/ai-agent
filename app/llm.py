import os

from dotenv import load_dotenv
from openai import OpenAI

from app.models import JobDescription
from app.prompts import build_jd_parse_messages
from app.structured_output import (
    build_tool_parameters_from_model,
    parse_and_validate,
)

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
    return parse_and_validate(
        tool_call.function.arguments,
        JobDescription,
    )
    
