"""Explicit model preparation only; normal inference never downloads assets."""

import json
from pathlib import Path
import shutil

from dishmook.backends import snapshot_fingerprint
from dishmook.runtime_models import ModelConfig


def preflight():
    try:
        import torch
    except ImportError:
        return {"ready":False,"reason":"Install the GPU dependencies in the free execution environment."}
    if not torch.cuda.is_available():
        return {"ready":False,"reason":"No CUDA GPU available; no paid fallback will be used."}
    return {"ready":True,"gpu_count":torch.cuda.device_count(),
            "devices":[{"index":i,"name":torch.cuda.get_device_name(i),
                        "vram_bytes":torch.cuda.get_device_properties(i).total_memory}
                       for i in range(torch.cuda.device_count())],
            "notice":"Hardware availability does not prove a host is free; use a confirmed free Kaggle session."}


def prepare_model(name, catalog, models_dir, *, download=False):
    data=json.loads(Path(catalog).read_text())
    matches=[c for c in data["candidates"] if c["name"]==name]
    if len(matches)!=1:
        raise ValueError("Unknown model candidate")
    candidate=matches[0]
    # Validate path components before creating or downloading anything.
    from pydantic import TypeAdapter
    from dishmook.domain import Identifier
    TypeAdapter(Identifier).validate_python(name)
    revision=candidate["revision"]
    if len(revision)!=40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("Candidate revision is not pinned")
    path=Path(models_dir).resolve()/name/revision
    if download:
        root=Path(models_dir).resolve()
        root.mkdir(parents=True,exist_ok=True)
        if shutil.disk_usage(root).free<20*1024**3 and not path.exists():
            raise ValueError("At least 20 GiB free local disk is required for this candidate snapshot")
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=candidate["model_id"],revision=revision,local_dir=str(path),
                          allow_patterns=["*.json","*.safetensors","*.model","*.txt","*.jinja","LICENSE*","README.md"],
                          token=False)
    if not path.is_dir():
        raise ValueError("Snapshot absent. Explicit --download or an attached local snapshot is required")
    if not list(path.glob("*.safetensors")):
        raise ValueError("Snapshot has no safetensors weights")
    return ModelConfig(backend="huggingface",model_id=candidate["model_id"],revision=revision,
                       local_path=str(path),snapshot_sha256=snapshot_fingerprint(path),device="cuda",quantization="nf4")
