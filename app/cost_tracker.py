from dataclasses import dataclass

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
)

from app.config import get_settings
from app.model_registry import estimate_cost
from app.metrics import metrics as http_metrics


class CostBudgetExceededError(RuntimeError):
    pass


@dataclass
class LlmUsageRecord:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    cached: bool


class CostTracker:
    def __init__(
        self,
        registry: CollectorRegistry | None = None,
        budget_usd: float = 0.0,
    ) -> None:
        self.registry = registry or CollectorRegistry(auto_describe=True)
        self.budget_usd = budget_usd

        self.total_cost_usd = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.records: list[LlmUsageRecord] = []

        self.llm_requests_total = Counter(
            "ai_job_agent_llm_requests_total",
            "Total LLM requests.",
            ["model", "cached"],
            registry=self.registry,
        )

        self.llm_tokens_total = Counter(
            "ai_job_agent_llm_tokens_total",
            "Total LLM input and output tokens.",
            ["model", "direction"],
            registry=self.registry,
        )

        self.llm_cost_usd_total = Counter(
            "ai_job_agent_llm_cost_usd_total",
            "Total estimated LLM cost in USD.",
            ["model"],
            registry=self.registry,
        )

        self.llm_latency_seconds = Histogram(
            "ai_job_agent_llm_latency_seconds",
            "LLM call latency in seconds.",
            ["model"],
            buckets=(
                0.1,
                0.25,
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
                20.0,
                30.0,
            ),
            registry=self.registry,
        )

    def record(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        cached: bool = False,
    ) -> LlmUsageRecord:
        cost_usd = estimate_cost(
            model,
            input_tokens,
            output_tokens,
        )

        if (
            self.budget_usd > 0
            and self.total_cost_usd + cost_usd > self.budget_usd
        ):
            raise CostBudgetExceededError(
                "LLM cost budget exceeded: "
                f"{self.total_cost_usd + cost_usd:.6f} > "
                f"{self.budget_usd:.6f}"
            )

        self.total_cost_usd += cost_usd
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        record = LlmUsageRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            cached=cached,
        )
        self.records.append(record)

        self.llm_requests_total.labels(
            model=model,
            cached=str(cached).lower(),
        ).inc()

        self.llm_tokens_total.labels(
            model=model,
            direction="input",
        ).inc(input_tokens)

        self.llm_tokens_total.labels(
            model=model,
            direction="output",
        ).inc(output_tokens)

        self.llm_cost_usd_total.labels(model=model).inc(cost_usd)
        self.llm_latency_seconds.labels(model=model).observe(
            latency_ms / 1000
        )

        return record


_default_cost_tracker: CostTracker | None = None


def get_default_cost_tracker() -> CostTracker:
    global _default_cost_tracker

    if _default_cost_tracker is None:
        settings = get_settings()
        _default_cost_tracker = CostTracker(
            registry=http_metrics.registry,
            budget_usd=settings.llm_cost_budget_usd,
        )   

    return _default_cost_tracker