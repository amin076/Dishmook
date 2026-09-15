# Scientific validity

Supported statuses: `supported`, `partially_supported`, `unsupported`, `contradicted`, `unverified`.

An assessed positive claim must reference verified supporting evidence and a named validator. A contradicted claim must reference verified opposing evidence and a validator. Raw model output cannot become verified Evidence. The Fake Backend always emits `unverified`.

These checks enforce record completeness, not the honesty or competence of a named validator. A real verification service with provenance checks remains future work. Confidence is finite and bounded to [0, 1]; it is not a calibrated probability.

No Phase 0 result demonstrates multi-agent benefit. Later evaluation must compare 1/5/10/20/50 agents under comparable budgets, include known-answer tasks, report failures and distinguish agreement from independent evidence.
