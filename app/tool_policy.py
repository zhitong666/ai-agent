from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ToolPermissionRule:
    tool_name: str
    risk: Literal["read", "write", "dangerous"] = "read"
    requires_approval: bool = False
    allowed: bool = True
    reason: str = ""


@dataclass(frozen=True)
class ToolPermissionDecision:
    tool_name: str
    allowed: bool
    requires_approval: bool
    reason: str = ""


class ToolPermissionPolicy:
    def __init__(
        self,
        rules: list[ToolPermissionRule] | None = None,
    ):
        self._rules: dict[str, ToolPermissionRule] = {}

        for rule in rules or []:
            self.register(rule)

    def register(self, rule: ToolPermissionRule) -> None:
        if rule.tool_name in self._rules:
            raise ValueError(f"duplicate tool permission rule: {rule.tool_name}")

        self._rules[rule.tool_name] = rule

    def check(
        self,
        tool_name: str,
        arguments: dict | None = None,
        scopes: set[str] | None = None,
    ) -> ToolPermissionDecision:
        rule = self._rules.get(tool_name)

        if rule is None:
            return ToolPermissionDecision(
                tool_name=tool_name,
                allowed=False,
                requires_approval=False,
                reason=f"unknown tool: {tool_name}",
            )

        if not rule.allowed:
            return ToolPermissionDecision(
                tool_name=tool_name,
                allowed=False,
                requires_approval=False,
                reason=rule.reason or "tool is disabled",
            )

        return ToolPermissionDecision(
            tool_name=tool_name,
            allowed=True,
            requires_approval=rule.requires_approval,
            reason=rule.reason,
        )


def build_default_tool_permission_policy() -> ToolPermissionPolicy:
    return ToolPermissionPolicy(
        [
            ToolPermissionRule(
                tool_name="search_knowledge",
                risk="read",
                requires_approval=False,
                allowed=True,
            ),
            ToolPermissionRule(
                tool_name="list_knowledge_titles",
                risk="read",
                requires_approval=False,
                allowed=True,
            ),
            ToolPermissionRule(
                tool_name="get_knowledge_document",
                risk="read",
                requires_approval=False,
                allowed=True,
            ),
            ToolPermissionRule(
                tool_name="apply_job",
                risk="dangerous",
                requires_approval=True,
                allowed=True,
                reason="投递岗位会影响外部系统，需要人工确认",
            ),
        ]
    )