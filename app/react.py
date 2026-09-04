import json 
import os 

from app.agent import format_context, get_retriever
from app.llm import client
from app.models import ReactResult, ReactStep

REACT_SYSTEM_PROMPT = """你是 AI 岗位咨询 Agent。
先用 search_knowledge 检索知识库，再根据检索结果回答。
只有当你已经能给出最终答案时，才调用 finish。"""

SEARCH_KNOWLEDGE_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": "在岗位知识库中检索与用户问题相关的内容。",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": "string", "description": "检索关键词或问题"},
            },
            "required": ["query"],
        },
    },
}

FINISH_TOOL = {
    "type": "function",
    "function": {
        "name": "finish",
        "description": "已经获得足够信息时，返回最终答案。",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "answer": {"type": "string", "description": "给用户的最终答案"},
            },
            "required": ["answer"],
        },
    },
}

TOOLS = [SEARCH_KNOWLEDGE_TOOL, FINISH_TOOL]


def _assistant_tool_message(tool_call, arguments, call_id):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            }
        ]
    }


def run_react_loop(question: str, retriever=None, max_steps: int = 5) -> ReactResult:
    retriever = retriever or get_retriever()
    messages = [
        {"role": "system", "content": REACT_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    steps: list[ReactStep] = []

    # max_steps 是简单但重要的防死循环护栏，Day18 会进一步扩展。
    for _ in range(max_steps):
        response = client.chat.completions.create(
            model=os.environ["OPENAI_MODEL"],
            messages=messages,
            tools=TOOLS,
            tool_choice="auto", # 模型可以自己选择调用哪个工具
        )

        message = response.choices[0].message

        if not message.tool_calls:
            raise RuntimeError("模型没有返回 tool_calls")

        tool_call = message.tool_calls[0]
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments or "{}")

        # 不追加消息，直接返回最终答案
        if tool_name == "finish":
            return ReactResult(answer=arguments.get("answer", ""), steps=steps)

        # 每次 search_knowledge 后，要把 assistant 的 tool call 和 role=tool 的结果都追加回 messages
        if tool_name == "search_knowledge":
            query = arguments.get("query") or question
            results = retriever.retrieve(query, top_k=3)
            observation = format_context(results)

            call_id = getattr(tool_call, "id", None) or f"call_{len(steps)}"

            steps.append(
                ReactStep(
                    action=tool_name,
                    action_input=query,
                    observation=observation,
                )
            )

            messages.append(_assistant_tool_message(tool_call, arguments, call_id))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id, # 不要遗漏 role=tool 的 tool_call_id，否则下一次模型调用可能无法正确关联工具结果
                    "content": observation,
                }
            )
            continue

        raise RuntimeError(f"未知工具: {tool_name}")

    raise RuntimeError("ReAct 循环超过最大步数")
