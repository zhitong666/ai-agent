import json
import os
import time

from openai import APIConnectionError, APITimeoutError, RateLimitError

from app.agent import get_retriever
from app.llm import client
from app.models import ReactResult, ReactStep
from app.tools import FINISH_TOOL_NAME, build_default_registry

REACT_SYSTEM_PROMPT = """你是 AI 岗位咨询 Agent。
先用 search_knowledge 或 list_knowledge_titles 了解知识库，再根据结果回答。
只有当你已经能给出最终答案时，才调用 finish。"""


def _tool_call_payload(tool_call, arguments, call_id):
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": tool_call.function.name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }


# 负责重试
def _call_model(messages, tools, max_retries, timeout):
    last_error = None

    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model=os.environ["OPENAI_MODEL"],
                messages=messages,
                tools=tools,
                tool_choice="auto",
                timeout=timeout,
            )
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            last_error = exc

            if attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))

    raise RuntimeError(f"模型调用失败，已重试 {max_retries} 次") from last_error


# llm_max_retries 和 timeout 通过参数传入，方便测试和以后调整
def run_react_loop(
    question: str, 
    retriever=None, 
    max_steps: int = 5,
    llm_max_retries: int = 3,
    timeout: int = 10,
) -> ReactResult:
    retriever = retriever or get_retriever()
    registry = build_default_registry()
    tools = registry.to_openai_tools()

    messages = [
        {"role": "system", "content": REACT_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    steps: list[ReactStep] = []

    for _ in range(max_steps):
        response = _call_model(messages, tools, llm_max_retries, timeout)

        message = response.choices[0].message

        if not message.tool_calls:
            raise RuntimeError("模型没有返回 tool_calls")

        assistant_tool_calls = []
        tool_result_messages = []

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments or "{}")

            if tool_name == FINISH_TOOL_NAME:
                return ReactResult(answer=arguments.get("answer", ""), steps=steps)

            tool = registry.get_tool(tool_name)

            if tool is None:
                raise RuntimeError(f"未知工具: {tool_name}")

            action_input = ""

            if tool.input_field:
                action_input = arguments.get(tool.input_field) or question

            # 工具执行放在 try/except 中，失败时降级为错误文本
            try: 
                observation = tool.handler(arguments, retriever=retriever)
            except Exception as exc:
                observation = f"工具 {tool_name} 执行失败: {exc}"

            call_id = getattr(tool_call, "id", None) or f"call_{len(steps)}"

            steps.append(
                ReactStep(
                    action=tool_name,
                    action_input=action_input,
                    observation=observation,
                )
            )

            assistant_tool_calls.append(
                _tool_call_payload(tool_call, arguments, call_id)
            )
            tool_result_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": observation,
                }
            )

        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": assistant_tool_calls,
            }
        )
        messages.extend(tool_result_messages)

    raise RuntimeError("ReAct 循环超过最大步数")