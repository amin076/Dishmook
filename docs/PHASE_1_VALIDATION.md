# Phase 1 validation

Local reference: Python 3.12.14, pytest 8.4.2, Pydantic 2.13.5.

- Base suite: 63 tests passed, including the 33 Phase 0 tests.
- Optional actual local adapter: 1 test passed with PyTorch 2.8.0+cpu and Transformers 4.57.1, using generated tiny safetensors weights. No pretrained model was downloaded.
- Fake CLI run completed and its candidate remained unverified.
- Windows/Linux and local-Hugging-Face CPU jobs are defined in GitHub Actions; use the PR checks for final remote acceptance.

Tests cover deterministic real-worker Fake output; timeout and child cleanup; worker failure; interruption with full reservation preserved; actual controller process death and lock release; recovery after result commit but before export; completed-run idempotence; malformed/model-invented verification JSON; prompt/output/attempt caps; secret redaction; traversal/symlink protection; concurrent controller rejection; append-only database events; truncated projection recovery; immutable spec integrity; and the local Hugging Face loader/tokenizer/generation path, including a spawned worker and changed-snapshot rejection.

These establish runtime mechanisms, not scientific accuracy, multi-agent benefit, model quality, GPU throughput or cross-GPU determinism. No paid API/GPU was used. GPU smoke, model selection, 4-bit support and Kaggle experiments remain future work.
