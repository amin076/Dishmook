# Phases 2–6: implementation and acceptance

| Phase | Implemented and locally checked | Remaining acceptance |
|---|---|---|
| 2 | Pinned 7B model catalog, explicit download, NF4 adapter, telemetry, model selection notebook | Run both candidates on GPU with the same known-answer protocol; no winner yet |
| 3 | Ten-role campaign, dependency context, budgets, pause/resume | Real-model end-to-end evaluation |
| 4 | Fifty distinct logical roles, staged groups, final editor, bounded dispute rounds, one/two workers | GPU and dual-GPU execution; useful real answers |
| 5 | 12 known-answer cases, three seeds, six profiles, paired case bootstrap, CSV/JSON reports | Real-model comparison; no scientific improvement established |
| 6 | Entry criteria documented below | Not started |

The full offline matrix completed 216 campaigns and 3,168 tasks without task failure. Fake outputs validate orchestration only: accuracy and improvement remain null. Fake usage counts UTF-8 bytes, not LLM tokens. Evidence records a dirty development revision; the final source commit captures that implementation plus subsequent documentation and fail-fast improvements. Local tests also include a tiny randomly initialized Hugging Face CPU model, which is not scientific model evidence.

## Kaggle connection

Import `notebooks/kaggle_model_selection.ipynb` into the existing Kaggle notebook environment. Set `SOURCE_REVISION` to the full reviewed source commit SHA and run the installation cell; it clones this repository at that exact revision. Alternatively attach `Dishmook-source.zip` as input `dishmook-source`. Check the actual input path in Kaggle and adjust the notebook variable if needed. Use a GPU session already available to you; the notebook does not provision services.

The notebook checks Python 3.12, GPU and disk, explicitly downloads pinned candidate weights, then runs the same benchmark for each. Preserve result files and checkpoint archives before the session ends. Selection requires completed real CUDA/NF4 measurements for two distinct models, comparable protocols and measured memory within the configured threshold. Ties or zero scores yield no winner. A selection is provisional on this small benchmark.

Add the resulting `model_selection.json` as input `dishmook-evidence` to `kaggle_campaign.ipynb`, adjusting the input path if necessary. That notebook prepares the selected snapshot and runs the six-profile comparison in resumable chunks. Neither notebook has been executed by this development environment on Kaggle.

The user supplied a screenshot of a separate T4 generation: 111 input tokens, 300 generated tokens, 17.63 seconds, 17.02 tokens/second, peak allocated VRAM 5.34 GB. This is user-reported execution evidence, not a reproduced Dishmook benchmark. Model ID, revision, quantization, complete answer and raw logs were not visible. The displayed answer stops during substitution, so correctness cannot be scored from it.

## Operational limits

All profiles share total input/output ceilings, not identical actual compute. Optional dispute rounds reserve a fixed share; unused reservations are not redistributed. Failed/unknown attempts retain their budget. Infrastructure failures stop the campaign; restoring infrastructure does not erase spent failed tasks. Use a fresh campaign for a complete new trial.

One or two persistent model processes serve logical roles. CPU/fake concurrency is tested; NF4 and dual-GPU execution are untested here. Role D proposes code/experiments but executes no generated code. Citation IDs and disagreements are tracked; this does not independently validate claims. Model snapshots are fully hashed on first load; subsequent cached calls check file metadata and rehash changes. Keep snapshots immutable on a trusted filesystem.

Archive only closed run folders, with no concurrent run creation. Restore into a new directory; keep the model at the recorded local path or reconstruct that path. Archives include checkpoints and reports, not weights. ZIP traversal/symlinks and oversized extraction are rejected. SQLite remains authoritative.

## Phase 6 entry criteria

Proceed only after real known-answer results demonstrate a defensible improvement under the stated budget, with failures, uncertainty and actual compute disclosed. Start with a bounded numerical problem with an analytic reference (for example a damped oscillator), independently run and check calculations, preserve counterexamples and unresolved disagreement. Generated assertions alone cannot satisfy this gate. No new scientific discovery is claimed.
