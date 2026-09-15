# Zero paid compute

Phase 0 supports only `dishmook-fake/v1`, running on CPU. `CostPolicy` rejects paid API, paid compute, network enablement and unsupported backend values. No credentials are read. The fixture's estimated service cost is exactly USD 0; this is not a measurement of electricity or the user's development subscriptions.

Kaggle is the planned quota-limited GPU target in the project specification. No current quota, GPU availability or model feasibility has been verified in Phase 0. Check these during Phase 2 before choosing a model. Unavailability must stop or defer execution; do not silently fall back to paid services. Do not commit weights, caches or large run output.
