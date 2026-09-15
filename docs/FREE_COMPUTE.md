> Historical Phase 1 description. For current campaign, NF4, Kaggle and evaluation behavior, see [phases 2–6](PHASES_2_TO_6.md).

# Zero paid compute

Phase 1 supports fake CPU execution and local Hugging Face on an existing CPU/CUDA device. Paid API/compute configurations are rejected. No remote endpoint, automatic download or paid fallback exists. No application API credentials are required.

Estimated service cost is USD 0 because Dishmook purchases no services. It cannot detect whether a host was rented elsewhere: use an owned machine or confirmed free quota. Electricity and development subscriptions are not measured. Wall time is recorded, not fabricated GPU billing.

Kaggle remains the planned quota-limited target. No GPU allocation or research model is selected in this phase. Unavailable CUDA fails with gpu_unavailable. Weights and run state are ignored by Git. Tests create tiny model weights only in temporary folders and use standard CPU CI runners.
