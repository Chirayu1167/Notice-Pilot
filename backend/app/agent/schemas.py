"""Agent schemas (Phase 4). Structured contracts between orchestrator, tools,
provider, guardrails, and API. No LLM calls here."""

from typing import Any, Literal

from pydantic import BaseModel, Field

Decision = Literal["CONTEST", "PARTIAL_ACCEPT", "INSUFFICIENT_EVIDENCE"]

ALLOWED_DECISIONS = ("CONTEST", "PARTIAL_ACCEPT", "INSUFFICIENT_EVIDENCE")

AGENT_STATES = (
    "IDLE",
    "ANALYZING",
    "INSPECTING_EVIDENCE",
    "EVALUATING",
    "WAITING_FOR_EVIDENCE",
    "READY_FOR_DRAFT",
    "DRAFT_READY",
    "HUMAN_REVIEW",
    "ERROR",
)

# Reconciliation status -> decisions the agent is allowed to select.
ALLOWED_BY_RECON_STATUS: dict[str, tuple[str, ...]] = {
    "MATCHED": ("CONTEST",),
    "PARTIAL": ("PARTIAL_ACCEPT", "INSUFFICIENT_EVIDENCE"),
    "UNEXPLAINED": ("INSUFFICIENT_EVIDENCE",),
    "MISSING_DATA": ("INSUFFICIENT_EVIDENCE",),
    "UNSUPPORTED": ("INSUFFICIENT_EVIDENCE",),
}

MAX_TOOL_ITERATIONS = 8


class MissingEvidenceItem(BaseModel):
    type: str = Field(description="RETURN_DOCUMENT | RESIDUAL_AMOUNT | PERIOD_CLARIFICATION")
    source: str | None = None
    period: str | None = None
    amount: float | None = None
    reason: str


class AgentDecision(BaseModel):
    decision: str
    reasoningSummary: str = ""
    findingIds: list[str] = Field(default_factory=list)
    evidenceIds: list[str] = Field(default_factory=list)
    missingEvidence: list[MissingEvidenceItem] = Field(default_factory=list)
    requiresHumanReview: bool = True


class AgentRunView(BaseModel):
    id: str
    noticeId: str
    status: str
    decision: str | None = None
    reasoningSummary: str | None = None
    requiresHumanReview: bool = True
    provider: str | None = None
    model: str | None = None
    toolIterations: int = 0
    error: str | None = None
    draftId: str | None = None
    createdAt: str | None = None
    completedAt: str | None = None


class AgentStepView(BaseModel):
    sequence: int
    tool: str
    purpose: str
    resultSummary: str
    status: str


class ReplyDraftView(BaseModel):
    id: str
    noticeId: str
    agentRunId: str | None = None
    decision: str | None = None
    content: str
    evidenceIds: list[str] = Field(default_factory=list)
    findingIds: list[str] = Field(default_factory=list)
    ruleVersion: str | None = None
    status: str = "draft"
    requiresReview: bool = True
    createdAt: str | None = None
    updatedAt: str | None = None


def as_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(k): as_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
