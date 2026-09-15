# Phase 1 — موتور تک‌ایجنتی

## Scope and acceptance

The user authorized this phase after Phase 0 passed CI. PR #1 was merged before this work.

Acceptance: reproducible single-agent Fake Backend execution; input/output and time limits; durable trace; interrupted-run recovery with conservative accounting; idempotent completed resume; a local-only Hugging Face adapter; offline Windows/Linux tests. A real GPU smoke is optional and has not been run. Choosing a research model and benchmarking Kaggle remain Phase 2.

## Design

A small `ModelBackend` protocol supports one problem and agent per immutable `ExecutionSpec`. Phase 0 fixture contracts remain backward compatible; Phase 1 introduces execution contracts and its own versioned manifest.

Inference uses a spawned child. The parent enforces the minimum of agent and execution time limits, including startup, imports, hashing and model loading. Terminate/kill cleanup may take four additional seconds. An orphan watcher ends the built-in worker when its parent dies. This is a killable model process, not a sandbox for arbitrary code.

SQLite transactions atomically commit state, results, accounting and append-only events. This adds `state.sqlite3` to the proposed file format instead of trying to make multiple JSON writes transactional. An OS file lock prevents two controllers for a run and is released on process death.

## Budget and resume

`max_input_tokens` applies to each attempt without silent truncation. The output cap is the minimum of per-attempt, agent and remaining total output limits. Attempt count and per-attempt wall time are also bounded.

The full allowed output is reserved before each model call. A valid usage response releases unused reservation even when its JSON is rejected. Unknown usage after interruption, timeout or backend failure retains the full reservation. Resume may retry only within the original remaining budget and attempt count. This may overcount actual usage but prevents free retries after interruption.

Fake token units are UTF-8 bytes, explicitly labeled `utf8_bytes`; Hugging Face counts real tokenizer IDs. Do not compare the two as model efficiency. `known_*_tokens` are measured; `unknown_reserved_tokens` is a conservative unknown-usage allowance. `total_output_tokens` does not include prompt tokens; each prompt has its own input cap.

The run folder contains `state.sqlite3`, `manifest.json`, `problem.json`, `plan.json`, `events.jsonl`, `claims.jsonl`, `trace.json`, `metrics.json`, `final_report.md`, and `run.lock`. No queue is needed for one task. SQLite is the authoritative checkpoint. Events cannot be updated/deleted through the application database schema. JSONL is a regenerated ordered export, not the journal's durability authority. `trace.json` is the latest attempt; committed events retain each request and available response.

Resume marks an uncommitted running attempt interrupted, preserves its reservation and optionally attempts again. A completed run exports its durable result without another model call or event. A failed run makes at most one new attempt per explicit resume. Exhausted runs cannot reset their budget. Truncated JSON exports are rebuilt from SQLite. The complete run directory must survive: JSON exports alone cannot restore a lost database. Copy the closed run folder between sessions; live copies and network filesystems are unsupported.

CLI exits: 0 completed/prepared; 1 recorded failure/exhaustion; 2 invalid configuration/path/storage; 130 keyboard interruption. Read the manifest's safe failure code. Raw model exception messages are suppressed.

## Local Hugging Face

For optional CPU inference, install in a separate environment:

```sh
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[dev,hf]"
python -m pytest -m hf
```

Prepare a trusted, licensed local model snapshot from its official source and record the exact 40-character repository revision. Dishmook does not download it. The directory needs safetensors weights and a tokenizer with a chat template. Custom Python code, pickle weights and 4-bit execution are unsupported in this phase. Use a small model on CPU.

```sh
python -m dishmook fingerprint-model /path/to/local/snapshot
```

Copy the example config and replace its `model` object, using real values:

```json
{
  "backend": "huggingface",
  "model_id": "OWNER/MODEL",
  "revision": "EXACT_40_CHARACTER_LOWERCASE_COMMIT_SHA",
  "local_path": "/path/to/local/snapshot",
  "snapshot_sha256": "EXACT_64_CHARACTER_LOWERCASE_SHA256",
  "device": "cpu",
  "quantization": "none"
}
```

Placeholders deliberately fail validation. The snapshot hash is recomputed before inference; changed assets fail. ID/revision are operator-supplied provenance, not authenticated by an offline hash. Keep the model immutable during execution. Run with `dishmook run --spec your-local-config.json`. Both agent and execution timeout must allow sufficient loading time.

An optional GPU smoke uses `device: cuda` on a confirmed free GPU machine with compatible PyTorch/CUDA. Unavailable CUDA fails; no paid rental/API fallback exists. CPU tests do not establish GPU determinism or research-model quality.

The model must return a JSON object containing only a nonempty `text` string. Markdown fences, non-JSON responses and invented verification/evidence fields are rejected. All accepted candidates are assigned `unverified` by the controller.

## Limits and next phase

No independent scientific validation, generated-code execution, multi-agent scheduling, persistent model pool, 4-bit model, benchmark or Kaggle deployment is included. Each attempt reloads its model in a fresh child, favoring killability over throughput. Phase 2 requires separate authorization.

Implementation references: [offline loading](https://huggingface.co/docs/transformers/v4.57.1/installation#offline-mode) and [chat templates](https://huggingface.co/docs/transformers/v4.57.1/chat_templating). Local-only loading and greedy generation are used; tokenizer template and asset hashes are recorded.
