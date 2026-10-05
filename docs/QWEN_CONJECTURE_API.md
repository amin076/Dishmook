# Local Qwen conjecture service

This experiment adds an optional local open-weight model to Dishmook without
changing the Phase-0 fake backend.

## Purpose

Dishmook proposes conjectures; Gareen must independently filter and prove them.
Raw model output is always marked `unverified`.

## GPU setup

Install:

```sh
pip install -e ".[research]"
```

Start the service:

```sh
uvicorn dishmook.api:app --host 0.0.0.0 --port 8000
```

The default model is `Qwen/Qwen2.5-7B-Instruct`. Override it with the
`DISHMOOK_QWEN_MODEL` environment variable.

POST `/v1/conjectures` with:

```json
{
  "parent_id": "T7",
  "parent_statement": "forall x y, x + y = y + x",
  "count": 20,
  "strategy": "neighborhood",
  "context_theorems": []
}
```

The response contains deduplicated, unverified candidates with parent
provenance, mutation labels, rationale and claimed neighborhood distance.

The service is intended to be the creative side of:
Dishmook -> Gareen -> Melakat -> Dishmook.
