# Reproducibility

Reference interpreter: Python 3.12.14. Direct package/test/build dependencies are pinned in `pyproject.toml`. Use a fresh virtual environment. A complete transitive lock and real model revision will be required before model benchmarking.

`python -m dishmook smoke --seed 42` returns byte-identical JSON for the same implementation and seed. Fake claim IDs use SHA-256 of canonical input and seed; they do not use Python's randomized hash. This is fixture determinism, not evidence for GPU determinism.

The smoke manifest records a fake model ID/revision, seed, active agents, budget configuration, cost policy and completion status. `code_revision` is honestly `unknown` because this fixture does not query Git. Real hardware metadata, timestamps, run persistence, append-only events and idempotent resume are deferred to the runtime phase. `smoke-run` is a fixed fixture label, not a unique production run identifier.
