"""Versioned single-agent execution contracts (separate from Phase 0 fixtures)."""

from typing import Literal

from pydantic import Field, model_validator

from dishmook.domain import Agent, Entity, PositiveInt, Problem, Text


class ModelConfig(Entity):
    backend: Literal["fake", "huggingface"] = "fake"
    model_id: Text = "dishmook-fake"
    revision: Text = "v1"
    local_path: str | None = None
    snapshot_sha256: str | None = None
    device: Literal["cpu", "cuda"] = "cpu"
    quantization: Literal["none"] = "none"
    # No paid endpoint, network download, custom code or pickle weights.
    paid_api_allowed: Literal[False] = False
    paid_compute_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_backend(self):
        import re
        if self.backend == "fake":
            if (self.model_id, self.revision, self.local_path, self.device) != ("dishmook-fake", "v1", None, "cpu"):
                raise ValueError("Fake backend metadata must identify the fixture")
            if self.snapshot_sha256 is not None:
                raise ValueError("Fake backend has no snapshot")
        elif not self.local_path or not re.fullmatch(r"[a-f0-9]{40}", self.revision):
            raise ValueError("Local Hugging Face requires a directory and pinned 40-character revision")
        elif not self.snapshot_sha256 or not re.fullmatch(r"[a-f0-9]{64}", self.snapshot_sha256):
            raise ValueError("Local Hugging Face requires an expected snapshot SHA-256")
        return self


class Limits(Entity):
    max_input_tokens: PositiveInt = 4096
    max_output_tokens: PositiveInt = 256
    total_output_tokens: PositiveInt = 512
    timeout_seconds: float = Field(default=30, gt=0, le=86400, allow_inf_nan=False)
    max_attempts: int = Field(default=2, strict=True, ge=1, le=10)


class ExecutionSpec(Entity):
    schema_version: Literal[1] = 1
    problem: Problem
    agent: Agent
    model: ModelConfig = Field(default_factory=ModelConfig)
    limits: Limits = Field(default_factory=Limits)
    seed: int = Field(default=0, strict=True, ge=0, le=2**32-1)


class ModelRequest(Entity):
    messages: list[dict[str, str]]
    seed: int
    max_input_tokens: PositiveInt
    max_output_tokens: PositiveInt


class ModelResponse(Entity):
    text: str = Field(max_length=262144)
    input_tokens: int = Field(strict=True, ge=0)
    output_tokens: int = Field(strict=True, ge=0)
    token_unit: Literal["utf8_bytes", "model_tokens"]
    metadata: dict = Field(default_factory=dict)


class Candidate(Entity):
    text: Text
