from unittest.mock import Mock

from app.mcp_agent_bridge import build_mcp_tool_registry
from app.tool_policy import (
    ToolPermissionDecision,
    ToolPermissionPolicy,
    ToolPermissionRule,
    build_default_tool_permission_policy,
)


def make_tools():
    return [
        {
            "name": "search_knowledge",
            "description": "Search knowledge.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "apply_job",
            "description": "Apply to a job.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "position": {"type": "string"},
                },
                "required": ["company", "position"],
            },
        },
    ]


def test_default_policy_allows_read_tools():
    policy = build_default_tool_permission_policy()

    decision = policy.check("search_knowledge")

    assert decision.allowed is True
    assert decision.requires_approval is False


def test_default_policy_requires_approval_for_apply_job():
    policy = build_default_tool_permission_policy()

    decision = policy.check("apply_job")

    assert decision.allowed is True
    assert decision.requires_approval is True


def test_default_policy_denies_unknown_tool():
    policy = build_default_tool_permission_policy()

    decision = policy.check("delete_all_data")

    assert decision.allowed is False
    assert "unknown tool" in decision.reason


def test_custom_policy_can_disable_tool():
    policy = ToolPermissionPolicy(
        [
            ToolPermissionRule(
                tool_name="search_knowledge",
                risk="read",
                allowed=False,
                reason="disabled for testing",
            )
        ]
    )

    decision = policy.check("search_knowledge")

    assert decision.allowed is False
    assert "disabled" in decision.reason


def test_registry_marks_dangerous_tool_requires_approval():
    registry = build_mcp_tool_registry(make_tools(), executor=lambda name, args: {})

    assert registry.get_tool("search_knowledge").requires_approval is False
    assert registry.get_tool("apply_job").requires_approval is True


def test_registry_hides_disabled_tool():
    policy = ToolPermissionPolicy(
        [
            ToolPermissionRule(
                tool_name="search_knowledge",
                risk="read",
                allowed=False,
            ),
            ToolPermissionRule(
                tool_name="apply_job",
                risk="dangerous",
                requires_approval=True,
                allowed=True,
            ),
        ]
    )

    registry = build_mcp_tool_registry(
        make_tools(),
        executor=lambda name, args: {},
        permission_policy=policy,
    )

    assert "search_knowledge" not in registry.tool_names()
    assert "apply_job" in registry.tool_names()


def test_remote_handler_checks_policy_before_execution():
    executor = Mock(return_value={"ok": True})
    policy = Mock()

    policy.check.side_effect = [
        ToolPermissionDecision(
            tool_name="search_knowledge",
            allowed=True,
            requires_approval=False,
        ),
        ToolPermissionDecision(
            tool_name="search_knowledge",
            allowed=False,
            requires_approval=False,
            reason="blocked at execution time",
        ),
    ]

    registry = build_mcp_tool_registry(
        make_tools()[:1],
        executor=executor,
        permission_policy=policy,
    )

    result = registry.get_tool("search_knowledge").handler(
        {"query": "FastAPI"},
        retriever=None,
    )

    assert "权限策略拒绝" in result
    executor.assert_not_called()