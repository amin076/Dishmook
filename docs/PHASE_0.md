# Phase 0 scope and acceptance

Plan: validate the initial repository, establish a Python package and contracts, implement a Fake Backend and CLI, then test locally and on Windows/Linux GitHub Actions.

Acceptance gates:

1. Editable package installation succeeds with Python 3.12.14.
2. All six entity schemas export valid JSON and reject invalid inputs.
3. The fixture smoke produces deterministic unverified output without external inference.
4. Tests pass on both GitHub Actions matrix platforms without GPU, API calls or credentials.

Implementation files: `pyproject.toml`, `.python-version`, `src/dishmook/`, `tests/`, `.github/workflows/ci.yml`, this documentation and the original Persian specification.

Phase 0 decisions: standard-library argparse for CLI; Pydantic contracts; pytest; no orchestration framework; no tool execution. Flat Python modules are intentional until later phases need larger packages. Direct dependencies and the reference Python version are pinned; transitive dependencies are not fully locked yet.

Limitations: token/timeout fields establish contracts only; no actual inference budgets are consumed or enforced. No queue, resume, persistence, real inference, 50-agent campaign or model benchmark exists yet. Those require later phases and their own tests. GitHub checkout and dependency installation use network; application tests do not. The specification's request for all of CI to run without internet is therefore interpreted as the test workload after setup, not the hosted runner lifecycle.

Do not enter Phase 1 until the Phase 0 gate is reviewed and the next phase is authorized.
