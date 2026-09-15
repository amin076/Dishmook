# Reproducibility

Reference interpreter: Python 3.12.14. Direct package/test/build dependencies are pinned in `pyproject.toml`. Use a fresh virtual environment. A complete transitive lock and real model revision will be required before model benchmarking.

Windows CI uses Python 3.12.10, explicitly pinned in the matrix: setup-python reported that 3.12.14 x64 is unavailable for Windows 2025. Linux CI and the local reference use 3.12.14. The root `.python-version` records the Linux reference; Windows developers should select 3.12.10 explicitly. This patch-version difference is tested, not silently treated as an identical environment.

`python -m dishmook smoke --seed 42` returns byte-identical JSON for the same implementation and seed. Fake claim IDs use SHA-256 of canonical input and seed; they do not use Python's randomized hash. This is fixture determinism, not evidence for GPU determinism.

The smoke manifest records a fake model ID/revision, seed, active agents, budget configuration, cost policy and completion status. `code_revision` is honestly `unknown` because this fixture does not query Git. Real hardware metadata, timestamps, run persistence, append-only events and idempotent resume are deferred to the runtime phase. `smoke-run` is a fixed fixture label, not a unique production run identifier.
