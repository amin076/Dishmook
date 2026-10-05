"""Conjecture-generation contracts.

Model output is creative input for Gareen. It is never mathematical evidence.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class ConjectureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_id: str
    parent_statement: str
    count: int = Field(default=10, ge=1, le=50)
    strategy: Literal["neighborhood", "generalize", "combine", "strengthen", "explore"] = "neighborhood"
    context_theorems: list[str] = Field(default_factory=list)

class ConjectureCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_id: str
    statement: str
    mutation_kind: str
    rationale: str
    claimed_distance: int = Field(default=1, ge=1, le=10)

class ConjectureBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str
    candidates: list[ConjectureCandidate]
    status: Literal["unverified"] = "unverified"
