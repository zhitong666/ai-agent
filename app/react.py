import json
import os

from app.agent import get_retriever
from app.llm import client
from app.models import ReactResult, ReactStep
from app.tools import FINISH_TOOL_NAME, build_default_registry

REACT_SYSTEM_PROMPT = """你是 AI 岗位咨询 Agent。
先用 search_knowledge 检索知识库，再根据检索结果回答。
只有当你已经能给出最终答案时，才调用 finish。"""


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
        ],
    }


def run_react_loop(question: str, retriever=None, max_steps: int = 5) -> ReactResult:
    retriever = retriever or get_retriever()
    registry = build_default_registry()
    tools = registry.to_openai_tools() # 不再写死工具列表

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
            tools=tools,
            tool_choice="auto", # 模型可以自己选择调用哪个工具
        )

        message = response.choices[0].message

        if not message.tool_calls:
            raise RuntimeError("模型没有返回 tool_calls")

        tool_call = message.tool_calls[0]
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments or "{}")

        # 不追加消息，直接返回最终答案
        if tool_name == FINISH_TOOL_NAME:
            return ReactResult(answer=arguments.get("answer", ""), steps=steps)

        tool = registry.get_tool(tool_name) # 找到工具

        if tool is None:
            raise RuntimeError(f"未知工具: {tool_name}")

        action_input = arguments.get(tool.input_field) or question # 通用写法，未来不同工具可以指定自己的输入字段
        observation = tool.handler(arguments, retriever=retriever) # 执行工具

        call_id = getattr(tool_call, "id", None) or f"call_{len(steps)}"

        steps.append(
            ReactStep(
                action=tool_name,
                action_input=action_input,
                observation=observation,
            )
        )

        messages.append(_assistant_tool_message(tool_call, arguments, call_id))
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": observation,
            }
        )

    raise RuntimeError("ReAct 循环超过最大步数")