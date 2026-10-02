from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class TaskInput(Input):
    project_id: Literal["notes-of-ashen", "ashen-courier"]
    message: str = Field(min_length=1, max_length=4000)
    mode: Literal["sandbox", "live"] = "sandbox"
    scenario: Literal["rag", "cache", "unknown"] = "rag"
    target_id: str | None = None


class MessageInput(Input):
    message: str = Field(min_length=1, max_length=4000)


class DraftInput(Input):
    version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=8000)


class DecisionInput(Input):
    version: int = Field(ge=1)
    decision: Literal["approve", "reject"]
    idempotency_key: str = Field(min_length=8, max_length=100)


class TicketInput(Input):
    status: Literal["closed"]


class Cause(Input):
    text: str
    citation_ids: list[str] = Field(default_factory=list)


class Answer(Input):
    action: Literal["answer", "clarify", "tool"]
    summary: str = Field(max_length=8000)
    facts: list[str] = Field(default_factory=list, max_length=20)
    causes: list[Cause] = Field(default_factory=list, max_length=10)
    steps: list[str] = Field(default_factory=list, max_length=20)
    missing_information: list[str] = Field(default_factory=list, max_length=10)
    citation_ids: list[str] = Field(default_factory=list, max_length=20)
    tool: Literal["simulate_health", "read_health"] | None = None
