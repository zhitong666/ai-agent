# 集中管理：
# - JD 解析的 few-shot Prompt。
# - 岗位分析的 Chain-of-Thought Prompt。
# - 聊天问答的 Prompt 构造。
import json

JD_PARSE_INSTRUCTIONS = """你是招聘信息解析器。
从用户提供的 JD 中提取结构化岗位信息。
必须调用 save_job_description 工具。
不要编造 JD 中不存在的信息。"""

JD_FEW_SHOT_EXAMPLES = [
    {
        "jd": "字节跳动招聘 AI Agent 工程师，要求掌握 Python 和 RAG，负责设计 Agent 工具调用流程。",
        "output": {
            "company": "字节跳动",
            "title": "AI Agent 工程师",
            "seniority": "mid",
            "responsibilities": ["设计 Agent 工具调用流程"],
            "requirements": ["Python", "RAG"],
            "keywords": ["AI Agent", "Python", "RAG"],
            "domain": "AI 应用",
        },
    }
]

ANALYSIS_INSTRUCTIONS = """你是 AI 岗位分析师。
根据岗位信息与知识库检索结果，生成岗位分析。
必须调用 save_job_analysis 工具。"""

COT_INSTRUCTIONS = """在生成结果前，先完成以下思考：
1. 这个岗位最核心的职责是什么
2. 我的技能与岗位要求相比，已经具备什么
3. 我还缺少什么
4. 面试可能重点考察什么
5. 应该按什么顺序补齐技能

思考完成后再调用 save_job_analysis 输出最终结果。"""

CHAT_INSTRUCTIONS = """你是 AI 岗位咨询助手。
根据知识库和对话历史回答用户问题，回答要简洁、准确。
如果使用了知识库内容，请在相关句子末尾用 [chunk_id] 标注来源。
如果知识库没有相关内容，就明确说明不知道。"""


def _format_few_shot_examples(examples: list[dict]) -> str:
    blocks = []

    for index, example in enumerate(examples, start=1):
        output = json.dumps(example["output"], ensure_ascii=False, indent=2)
        blocks.append(
            f"示例 {index} 输入 JD：\n{example['jd']}\n"
            f"示例 {index} 输出 JSON：\n{output}"
        )

    return "\n\n".join(blocks)


def build_jd_parse_messages(jd_text: str) -> list[dict]:
    system = (
        JD_PARSE_INSTRUCTIONS
        + "\n\n以下示例只用于说明格式，不要照搬示例内容。\n"
        + _format_few_shot_examples(JD_FEW_SHOT_EXAMPLES)
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": jd_text},
    ]


def build_analysis_messages(job, context: str, cot: bool = True) -> list[dict]:
    instructions = ANALYSIS_INSTRUCTIONS

    if cot:
        instructions = f"{instructions}\n\n{COT_INSTRUCTIONS}"

    user_content = f"岗位信息：\n{job.model_dump_json()}\n\n知识库：\n{context}"

    return [
        {"role": "system", "content": instructions},
        {"role": "user", "content": user_content},
    ]


def build_chat_messages(
    history: list[dict],
    context: str,
    question: str,
) -> list[dict]:
    return [
        {"role": "system", "content": CHAT_INSTRUCTIONS},
        *history,
        {"role": "user", "content": f"知识库：\n{context}\n\n问题：{question}"},
    ]