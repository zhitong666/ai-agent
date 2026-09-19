from dataclasses import dataclass

from app.guards import validate_tool_arguments


@dataclass
class ToolExecutionResult:
    ok: bool
    observation: str


def execute_registered_tool(
    tool,
    arguments,
    retriever,
    approve_tool_call=None
):
    guard_error = validate_tool_arguments(tool.name, arguments)

    if guard_error:
        return ToolExecutionResult(
            False,
            f"工具 {tool.name} 参数校验失败: {guard_error}",
        )

    try:
        if tool.requires_approval:
            if approve_tool_call is None:
                return ToolExecutionResult(
                    False,
                    f"工具 {tool.name} 需要人工确认，但当前没有审批处理程序。",
                )

            if not approve_tool_call(tool.name, arguments):
                return ToolExecutionResult(False, f"工具 {tool.name} 已被用户拒绝。")

        observation = tool.handler(arguments, retriever=retriever)
        return ToolExecutionResult(True, observation)
    except Exception as exc:
        return ToolExecutionResult(
            False,
            f"工具 {tool.name} 执行失败: {exc}",
        )