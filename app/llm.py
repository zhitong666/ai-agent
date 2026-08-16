import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from app.models import JobDescription

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

SYSTEM_PROMPT = """你是招聘信息解析器。
从用户提供的 JD 中提取结构化字段。

必须返回一个 JSON 对象，字段如下：
- company：公司名
- title：岗位名称
- seniority：只能是 junior、mid、senior、staff、unknown
- responsibilities：职责列表
- requirements：任职要求列表
- keywords：技术关键词列表
- domain：业务领域，没有则为空字符串

不要输出 Markdown 代码块，不要输出任何解释。"""

def parse_job_description(jd_text: str) -> JobDescription:
    response = client.chat.completions.create(
        model=os.environ["OPENAI_MODEL"],
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": jd_text},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    content = response.choices[0].message.content
    data = json.loads(content)
    return JobDescription.model_validate(data)
