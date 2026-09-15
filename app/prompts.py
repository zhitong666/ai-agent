# 集中管理：
# - JD 解析的 few-shot Prompt。
# - 岗位分析的 Chain-of-Thought Prompt。
# - 聊天问答的 Prompt 构造。
import json

from app.prompt_library import PromptLibrary, PromptTemplate

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


PROMPT_LIBRARY = PromptLibrary()

PROMPT_LIBRARY.register(
    PromptTemplate(
        name="jd_parse_system",
        version="v1",
        description="JD 解析系统提示",
        content=(
            JD_PARSE_INSTRUCTIONS
            + "\n\n以下示例只用于说明格式，不要照搬示例内容。\n{examples}"
        ),
    )
)

PROMPT_LIBRARY.register(
    PromptTemplate(
        name="analysis_system",
        version="v1",
        description="岗位分析系统提示",
        content="{base_instructions}\n\n{cot_instructions}",
    )
)

PROMPT_LIBRARY.register(
    PromptTemplate(
        name="analysis_user",
        version="v1",
        description="岗位分析用户消息",
        content="岗位信息：\n{job_json}\n\n知识库：\n{context}",
    )
)

PROMPT_LIBRARY.register(
    PromptTemplate(
        name="chat_system",
        version="v1",
        description="聊天系统提示",
        content=CHAT_INSTRUCTIONS,
    )
)

PROMPT_LIBRARY.register(
    PromptTemplate(
        name="chat_user",
        version="v1",
        description="聊天用户消息",
        content="知识库：\n{context}\n\n问题：{question}",
    )
)


def build_jd_parse_messages(jd_text: str) -> list[dict]:
    system = PROMPT_LIBRARY.render(
        "jd_parse_system",
        examples=_format_few_shot_examples(JD_FEW_SHOT_EXAMPLES),
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": jd_text},
    ]


def build_analysis_messages(job, context: str, cot: bool = True) -> list[dict]:
    if cot:
        instructions = PROMPT_LIBRARY.render(
            "analysis_system",
            base_instructions=ANALYSIS_INSTRUCTIONS,
            cot_instructions=COT_INSTRUCTIONS,
        )
    else:
        instructions = ANALYSIS_INSTRUCTIONS

    user_content = PROMPT_LIBRARY.render(
        "analysis_user",
        job_json=job.model_dump_json(),
        context=context,
    )

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
        {
            "role": "system",
            "content": PROMPT_LIBRARY.render("chat_system"),
        },
        *history,
        {
            "role": "user",
            "content": PROMPT_LIBRARY.render(
                "chat_user",
                context=context,
                question=question,
            ),
        },
    ]


PLANNER_INSTRUCTIONS = """你是任务规划器。只生成计划，不直接回答用户问题。
把用户问题拆成 1 到 5 个可执行步骤。
每一步必须从可用工具中选择一个工具。
Day 43 只允许使用 search_knowledge 和 list_knowledge_titles。

输入规则：
- search_knowledge 的 input 必须是具体检索关键词或问题，禁止留空。
- list_knowledge_titles 的 input 必须留空。

示例：
- 如果用户问“AI Agent 需要补什么”，search_knowledge 的 input 可以是“AI Agent 技能要求”。
- 如果需要先了解知识库主题，可以先用 list_knowledge_titles。

最后不要生成总结步骤，总结由执行器完成。"""

PLAN_FINAL_ANSWER_INSTRUCTIONS = """你是任务执行者。
根据已完成的计划步骤和观察结果生成最终答案。
只使用计划中已经获得的信息，不要编造。
如果计划没有获得足够信息，就明确说明目前信息不足。"""


PROMPT_LIBRARY.register(
    PromptTemplate(
        name="plan_system",
        version="v1",
        description="Plan-and-Execute 规划器系统提示",
        content=PLANNER_INSTRUCTIONS + "\n\n可用工具：\n{tool_catalog}",
    )
)

PROMPT_LIBRARY.register(
    PromptTemplate(
        name="plan_user",
        version="v1",
        description="Plan-and-Execute 规划器用户消息",
        content="用户问题：\n{question}",
    )
)

PROMPT_LIBRARY.register(
    PromptTemplate(
        name="plan_final_system",
        version="v1",
        description="Plan-and-Execute 最终答案系统提示",
        content=PLAN_FINAL_ANSWER_INSTRUCTIONS,
    )
)

PROMPT_LIBRARY.register(
    PromptTemplate(
        name="plan_final_user",
        version="v1",
        description="Plan-and-Execute 最终答案用户消息",
        content="用户问题：\n{question}\n\n计划执行轨迹：\n{trace}",
    )
)


def build_plan_messages(question: str, tool_catalog: str) -> list[dict]:
    system = PROMPT_LIBRARY.render(
        "plan_system",
        tool_catalog=tool_catalog,
    )

    user = PROMPT_LIBRARY.render(
        "plan_user",
        question=question,
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_plan_final_answer_messages(question: str, trace: str) -> list[dict]:
    system = PROMPT_LIBRARY.render("plan_final_system")

    user = PROMPT_LIBRARY.render(
        "plan_final_user",
        question=question,
        trace=trace,
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


SUPERVISOR_INSTRUCTIONS = """你是 Supervisor。只负责判断交给哪个 Worker，不直接回答用户问题。
只能从可用 Worker 中选择一个。
如果问题是 JD 文本、岗位分析、职位要求，选择 jd_analysis。
如果问题是知识库问答、学习路径、技能补充，选择 knowledge。"""

PROMPT_LIBRARY.register(
    PromptTemplate(
        name="supervisor_system",
        version="v1",
        description="Supervisor 系统提示",
        content=SUPERVISOR_INSTRUCTIONS + "\n\n可用 Worker：\n{worker_catalog}",
    )
)

PROMPT_LIBRARY.register(
    PromptTemplate(
        name="supervisor_user",
        version="v1",
        description="Supervisor 用户消息",
        content="用户问题：\n{question}",
    )
)


def build_supervisor_messages(
    question: str,
    worker_catalog: str,
) -> list[dict]:
    system = PROMPT_LIBRARY.render(
        "supervisor_system",
        worker_catalog=worker_catalog,
    )

    user = PROMPT_LIBRARY.render(
        "supervisor_user",
        question=question,
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]