"""Local-only model adapter. No API client and no automatic download."""

import hashlib
import json
import os
import time
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
        if file.is_file() and ".cache" not in file.relative_to(path).parts:
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
        self._cache = None
        self._signature = None

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
        if self.config.device == "cuda" and (not torch.cuda.is_available() or self.config.cuda_index >= torch.cuda.device_count()):
            raise BackendError("gpu_unavailable")
        signature = [(f.relative_to(path).as_posix(), f.stat().st_size, f.stat().st_mtime_ns)
                     for f in sorted(path.rglob("*")) if f.is_file() and ".cache" not in f.relative_to(path).parts]
        load_started = time.monotonic()
        device = f"cuda:{self.config.cuda_index}" if self.config.device == "cuda" else "cpu"
        if self._cache is None or signature != self._signature:
            fingerprint = snapshot_fingerprint(path)
            if fingerprint != self.config.snapshot_sha256:
                raise BackendError("model_snapshot_changed")
            tokenizer = transformers.AutoTokenizer.from_pretrained(
                str(path), local_files_only=True, trust_remote_code=False)
            if not tokenizer.chat_template:
                raise BackendError("chat_template_missing")
            kwargs = dict(local_files_only=True, trust_remote_code=False, use_safetensors=True)
            if self.config.quantization == "nf4":
                kwargs.update(quantization_config=transformers.BitsAndBytesConfig(
                    load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16),
                    device_map={"": self.config.cuda_index})
            model = transformers.AutoModelForCausalLM.from_pretrained(str(path), **kwargs)
            if self.config.quantization == "none":
                model.to(device)
            model.eval()
            self._cache = (tokenizer, model, fingerprint)
            self._signature = signature
        tokenizer, model, fingerprint = self._cache
        load_seconds = time.monotonic() - load_started
        prompt = tokenizer.apply_chat_template(request.messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
        input_tokens = inputs["input_ids"].shape[-1]
        if input_tokens > request.max_input_tokens:
            raise BackendError("input_budget_exceeded")
        torch.manual_seed(request.seed)
        context = getattr(model.config, "max_position_embeddings", None)
        if context is not None and input_tokens + request.max_output_tokens > context:
            raise BackendError("model_context_exceeded")
        inputs = {key: value.to(device) for key, value in inputs.items()}
        if self.config.device == "cuda":
            torch.cuda.synchronize(self.config.cuda_index)
            torch.cuda.reset_peak_memory_stats(self.config.cuda_index)
        generation_started = time.monotonic()
        with torch.inference_mode():
            outputs = model.generate(**inputs, max_new_tokens=request.max_output_tokens,
                                     do_sample=False, num_beams=1, num_return_sequences=1,
                                     pad_token_id=tokenizer.eos_token_id)
        if self.config.device == "cuda":
            torch.cuda.synchronize(self.config.cuda_index)
        generation_seconds = time.monotonic() - generation_started
        generated = outputs[0][input_tokens:]
        return ModelResponse(text=tokenizer.decode(generated, skip_special_tokens=True),
                             input_tokens=input_tokens, output_tokens=len(generated), token_unit="model_tokens",
                             metadata={"snapshot_sha256": fingerprint,
                                       "chat_template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
                                       "torch_version": torch.__version__,
                                       "transformers_version": transformers.__version__,
                                       "device": device,
                                       "quantization": self.config.quantization,
                                       "load_seconds": load_seconds, "generation_seconds": generation_seconds,
                                       "peak_vram_bytes": torch.cuda.max_memory_allocated(self.config.cuda_index) if self.config.device == "cuda" else None,
                                       "gpu_name": torch.cuda.get_device_name(self.config.cuda_index) if self.config.device == "cuda" else None})


def create_backend(config: ModelConfig) -> ModelBackend:
    config = ModelConfig.model_validate(config.model_dump())
    return FakeBackend() if config.backend == "fake" else HuggingFaceBackend(config)
