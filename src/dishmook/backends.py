"""Local-only model adapter. No API client and no automatic download."""

import hashlib
import json
import os
from pathlib import Path
from typing import Protocol

from dishmook.runtime_models import ModelConfig, ModelRequest, ModelResponse


class BackendError(Exception):
    """An error with a public, input-free code."""


class ModelBackend(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse: ...


class FakeBackend:
    def generate(self, request: ModelRequest) -> ModelResponse:
        payload = json.dumps(request.messages, sort_keys=True, ensure_ascii=False)
        count = len(payload.encode("utf-8"))
        if count > request.max_input_tokens:
            raise BackendError("input_budget_exceeded")
        digest = hashlib.sha256(f"{request.seed}:{payload}".encode()).hexdigest()[:16]
        text = json.dumps({"text": f"FAKE candidate {digest}; no scientific solution."})
        # Byte tokenizer is explicit, deterministic and unrelated to any real LLM tokenizer.
        raw = text.encode()[:request.max_output_tokens]
        return ModelResponse(text=raw.decode(), input_tokens=count, output_tokens=len(raw),
                             token_unit="utf8_bytes", metadata={"backend_version": "v1"})


def snapshot_fingerprint(path: Path) -> str:
    """Fingerprint all local assets; names, content and changes are significant."""
    digest = hashlib.sha256()
    files = sorted(path.rglob("*"))
    for file in files:
        if file.is_file():
            # HF cache symlinks are allowed; target bytes, not link names, are hashed.
            file_digest = hashlib.sha256()
            with file.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    file_digest.update(chunk)
            digest.update(json.dumps([file.relative_to(path).as_posix(), file_digest.hexdigest()],
                                     ensure_ascii=False).encode())
            digest.update(b"\n")
    return digest.hexdigest()


class HuggingFaceBackend:
    def __init__(self, config: ModelConfig):
        self.config = config

    def generate(self, request: ModelRequest) -> ModelResponse:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        path = Path(self.config.local_path).resolve()
        if not path.is_dir():
            raise BackendError("local_model_missing")
        try:
            import torch
            import transformers
        except ImportError:
            raise BackendError("local_backend_dependencies_missing") from None
        if self.config.device == "cuda" and not torch.cuda.is_available():
            raise BackendError("gpu_unavailable")
        fingerprint = snapshot_fingerprint(path)
        if fingerprint != self.config.snapshot_sha256:
            raise BackendError("model_snapshot_changed")
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            str(path), local_files_only=True, trust_remote_code=False)
        if not tokenizer.chat_template:
            raise BackendError("chat_template_missing")
        prompt = tokenizer.apply_chat_template(request.messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
        input_tokens = inputs["input_ids"].shape[-1]
        if input_tokens > request.max_input_tokens:
            raise BackendError("input_budget_exceeded")
        torch.manual_seed(request.seed)
        model = transformers.AutoModelForCausalLM.from_pretrained(
            str(path), local_files_only=True, trust_remote_code=False, use_safetensors=True)
        model.to(self.config.device)
        model.eval()
        context = getattr(model.config, "max_position_embeddings", None)
        if context is not None and input_tokens + request.max_output_tokens > context:
            raise BackendError("model_context_exceeded")
        inputs = {key: value.to(self.config.device) for key, value in inputs.items()}
        with torch.inference_mode():
            outputs = model.generate(**inputs, max_new_tokens=request.max_output_tokens,
                                     do_sample=False, num_beams=1, num_return_sequences=1,
                                     pad_token_id=tokenizer.eos_token_id)
        generated = outputs[0][input_tokens:]
        return ModelResponse(text=tokenizer.decode(generated, skip_special_tokens=True),
                             input_tokens=input_tokens, output_tokens=len(generated), token_unit="model_tokens",
                             metadata={"snapshot_sha256": fingerprint,
                                       "chat_template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
                                       "torch_version": torch.__version__,
                                       "transformers_version": transformers.__version__,
                                       "device": self.config.device,
                                       "gpu_name": torch.cuda.get_device_name(0) if self.config.device == "cuda" else None})


def create_backend(config: ModelConfig) -> ModelBackend:
    config = ModelConfig.model_validate(config.model_dump())
    return FakeBackend() if config.backend == "fake" else HuggingFaceBackend(config)
