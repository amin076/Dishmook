"""Small HTTP API for local conjecture generation."""
from __future__ import annotations
import os
from fastapi import FastAPI
from dishmook.conjectures import ConjectureBatch, ConjectureRequest
from dishmook.qwen_backend import QwenConjectureBackend

app = FastAPI(title="Dishmook Conjecture API", version="0.1.0")
_backend = None

def get_backend():
    global _backend
    if _backend is None:
        _backend = QwenConjectureBackend(
            model_id=os.getenv("DISHMOOK_QWEN_MODEL", "Qwen/Qwen2.5-7B-Instruct")
        )
    return _backend

@app.get("/health")
def health():
    return {"status": "ok", "backend": "qwen", "model_loaded": _backend is not None}

@app.post("/v1/conjectures", response_model=ConjectureBatch)
def conjectures(request: ConjectureRequest):
    return get_backend().generate_conjectures(request)
