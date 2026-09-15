> Historical Phase 1 description. For current campaign, NF4, Kaggle and evaluation behavior, see [phases 2–6](PHASES_2_TO_6.md).

# Reproducibility — Phase 1

Linux reference: Python 3.12.14 (`.python-version`). Windows CI: 3.12.10 because setup-python has no Windows 2025 x64 build of 3.12.14. Direct dependencies are pinned, including optional Transformers 4.57.1/PyTorch 2.8.0. Transitive dependencies are not fully locked; record a full environment before research benchmarking.

Fake claims and known usage are identical for identical sanitized input, agent instructions and seed. Canonical messages are hashed instead of Python's randomized hash. Run IDs, timestamps, hardware and wall times intentionally differ. Phase 0 smoke remains byte-identical.

The real adapter uses greedy generation and a seed. It checks local asset SHA-256 and records chat-template SHA-256 and library versions. CUDA determinism across devices is not guaranteed. The generated tiny CPU fixture tests integration, not scientific quality.

The execution spec is hashed and immutable on resume. The manifest records initial Git revision, model ID/revision, seed, limits, agent, hardware, times and outcomes; attempts record their own code revisions. Git is unknown outside a checkout. RAM is host physical memory, not a cgroup allocation. Unavailable metadata is null. Attempt wall time is not GPU utilization or billed time.

An uncommitted working tree appends `-dirty` to the recorded Git revision; it must not be presented as a clean reproducible commit.

Transactions ensure at most one committed result for this single task. Interrupted attempts can execute again within limits: exactly-once model execution is not claimed. Unknown usage retains its full allowance. Preserve the complete closed run directory, especially state.sqlite3. JSON exports alone are insufficient. Filesystem loss, live cross-machine copying and unreliable disks are outside this phase.
