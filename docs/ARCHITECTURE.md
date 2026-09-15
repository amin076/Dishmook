# Architecture — Phase 1

`domain.py` owns research entities; `runtime_models.py` owns execution contracts. `backends.py` supplies fake/local-Hugging-Face generation through a small protocol. `worker.py` provides killable inference. `runtime.py` applies budgets, parsing and lifecycle transitions. `storage.py` owns the transaction and lock. `cli.py` exposes run/prepare/resume and utilities.

The controller validates/redacts a spec, prepares the run and reserves output allowance transactionally. A child returns text and usage. The controller parses a minimal candidate, assigns unverified status, commits result/state/events atomically, and exports human-readable files. Resume returns a completed result, starts another bounded attempt or marks budget exhaustion.

The Phase 0 smoke remains a fixture. Shared model pools, scheduling, 50 agent roles, retrieval and comparative evaluation are future phases.
