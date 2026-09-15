"""Validated data contracts; schema validity does not establish scientific truth."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Problem(Entity):
    problem_id: Identifier
    title: Text
    statement: Text
    assumptions: list[Text] = Field(default_factory=list)
    documents: list[Text] = Field(default_factory=list)


class Agent(Entity):
    agent_id: Identifier
    role: Text
    instructions: Text
    allowed_tools: list[Literal["none"]] = Field(default_factory=list)
    max_output_tokens: PositiveInt = 256
    timeout_seconds: PositiveInt = 30


class Task(Entity):
    task_id: Identifier
    problem_id: Identifier
    agent_id: Identifier
    input_text: Text
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    failure_reason: Text | None = None

    @model_validator(mode="after")
    def failure_has_reason(self):
        if self.status == "failed" and self.failure_reason is None:
            raise ValueError("A failed task must record its reason")
        if self.status != "failed" and self.failure_reason is not None:
            raise ValueError("Only failed tasks may have a failure reason")
        return self


class Evidence(Entity):
    evidence_id: Identifier
    kind: Literal["document", "calculation", "test", "model_output"]
    source: Text
    description: Text
    validator: Text | None = None
    verified: bool = False

    @model_validator(mode="after")
    def verification_requires_validator(self):
        if self.verified and (self.validator is None or self.kind == "model_output"):
            raise ValueError("Verified evidence requires a validator and cannot be raw model output")
        return self


class Claim(Entity):
    claim_id: Identifier
    text: Text
    producer_agent_id: Identifier
    supporting_evidence: list[Evidence] = Field(default_factory=list)
    opposing_evidence: list[Evidence] = Field(default_factory=list)
    calculations: list[Text] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    status: Literal["supported", "partially_supported", "unsupported", "contradicted", "unverified"] = "unverified"
    validator: Text | None = None

    @model_validator(mode="after")
    def evidence_required_for_assessment(self):
        if self.status in {"supported", "partially_supported", "contradicted"}:
            evidence = self.opposing_evidence if self.status == "contradicted" else self.supporting_evidence
            if self.validator is None or not any(item.verified for item in evidence):
                raise ValueError("Assessed claims require a validator and relevant verified evidence")
        return self


class CostPolicy(Entity):
    # Literal false rejects configuration that would enable paid services.
    paid_compute_allowed: Literal[False] = False
    paid_api_allowed: Literal[False] = False
    backend: Literal["fake"] = "fake"
    network_allowed: Literal[False] = False


class Run(Entity):
    run_id: Identifier
    problem_id: Identifier
    seed: int = Field(default=0, strict=True, ge=0)
    model_id: Literal["dishmook-fake"] = "dishmook-fake"
    model_revision: Literal["v1"] = "v1"
    quantization: Literal["none"] = "none"
    code_revision: Text = "unknown"
    active_agents: list[Identifier] = Field(min_length=1)
    max_output_tokens: PositiveInt = 256
    status: Literal["created", "completed", "failed"] = "created"
    failure_reason: Text | None = None
    estimated_cost_usd: Literal[0] = 0
    policy: CostPolicy = Field(default_factory=CostPolicy)

    @model_validator(mode="after")
    def check_run(self):
        if len(set(self.active_agents)) != len(self.active_agents):
            raise ValueError("Active agent IDs must be unique")
        if (self.status == "failed") != (self.failure_reason is not None):
            raise ValueError("Failure reason is required exactly when a run failed")
        return self
