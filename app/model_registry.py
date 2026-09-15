from dataclasses import dataclass
from typing import Literal

TaskName = Literal[
    "jd_parse",
    "job_analysis",
    "chat",
    "agent",
    "planner",
    "plan_final_answer",
    "supervisor",
]
LatencyTier = Literal["low", "medium", "high"]


class ModelRegistryError(ValueError):
    """模型注册表或模型选择失败时抛出。"""


@dataclass(frozen=True)
class ModelProfile:
    name: str
    provider: str
    input_cost_per_million: float
    output_cost_per_million: float
    context_window: int
    supports_tools: bool
    supports_streaming: bool
    latency: LatencyTier
    capabilities: tuple[str, ...] = ()


MODEL_REGISTRY: dict[str, ModelProfile] = {
    "deepseek-chat": ModelProfile(
        name="deepseek-chat",
        provider="DeepSeek",
        input_cost_per_million=0.27,
        output_cost_per_million=1.10,
        context_window=64000,
        supports_tools=True,
        supports_streaming=True,
        latency="low",
        capabilities=("chat", "structured", "agent"),
    ),
    "deepseek-reasoner": ModelProfile(
        name="deepseek-reasoner",
        provider="DeepSeek",
        input_cost_per_million=0.55,
        output_cost_per_million=2.19,
        context_window=64000,
        supports_tools=True,
        supports_streaming=True,
        latency="medium",
        capabilities=("reasoning", "analysis"),
    ),
}

LATENCY_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
}

TASK_REQUIREMENTS = {
    "jd_parse": {
        "requires_tools": True,
        "requires_streaming": False,
        "max_latency": "low",
        "capabilities": {"structured"},
    },
    "job_analysis": {
        "requires_tools": True,
        "requires_streaming": False,
        "max_latency": "high",
        "capabilities": {"analysis"},
    },
    "chat": {
        "requires_tools": False,
        "requires_streaming": True,
        "max_latency": "low",
        "capabilities": set(),
    },
    "agent": {
        "requires_tools": True,
        "requires_streaming": True,
        "max_latency": "low",
        "capabilities": set(),
    },
    "planner": {
        "requires_tools": True,
        "requires_streaming": False,
        "max_latency": "low",
        "capabilities": {"structured"},
    },
    "plan_final_answer": {
        "requires_tools": False,
        "requires_streaming": False,
        "max_latency": "low",
        "capabilities": set(),
    },
    "supervisor": {
        "requires_tools": True,
        "requires_streaming": False,
        "max_latency": "low",
        "capabilities": {"structured"},
    },
}


def get_model_profile(name: str) -> ModelProfile:
    profile = MODEL_REGISTRY.get(name)

    if profile is None:
        raise ModelRegistryError(f"未知模型：{name}")

    return profile


def select_model(task: str) -> str:
    requirements = TASK_REQUIREMENTS.get(task)

    if requirements is None:
        raise ModelRegistryError(f"未知任务：{task}")

    candidates = []

    for profile in MODEL_REGISTRY.values():
        if requirements["requires_tools"] and not profile.supports_tools:
            continue

        if requirements["requires_streaming"] and not profile.supports_streaming:
            continue

        if LATENCY_ORDER[profile.latency] > LATENCY_ORDER[requirements["max_latency"]]:
            continue

        if not requirements["capabilities"].issubset(set(profile.capabilities)):
            continue

        candidates.append(profile)

    if not candidates:
        raise ModelRegistryError(f"没有模型满足任务要求：{task}")

    return min(
        candidates,
        key=lambda profile: (
            LATENCY_ORDER[profile.latency],
            profile.input_cost_per_million,
            profile.output_cost_per_million,
        ),
    ).name


def get_model_name(task: str, override: str | None = None) -> str:
    if override:
        return override

    return select_model(task)


def estimate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    profile = get_model_profile(model_name)

    input_cost = input_tokens * profile.input_cost_per_million / 1_000_000
    output_cost = output_tokens * profile.output_cost_per_million / 1_000_000

    return round(input_cost + output_cost, 6)