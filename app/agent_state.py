from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.models import ReactStep

class AgentState(BaseModel):
    question: str
    status: Literal["running", "finished", "failed"] = "running"
    steps: list[ReactStep] = Field(default_factory=list)
    final_answer: str | None = None

    def mark_running(self) -> None:
        self.status = "running"
    
    def mark_finished(self, answer: str) -> None:
        self.final_answer = answer
        self.status = "finished"

    def mark_failed(self) -> None:
        self.status = "failed"


def save_checkpoint(state: AgentState, path: Path) -> None:
    # 把 Pydantic 对象转成 JSON 字符串
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")


def load_checkpoint(path: Path) -> AgentState:
    # 把 JSON 字符串读回 Pydantic 对象
    return AgentState.model_validate_json(path.read_text(encoding="utf-8"))