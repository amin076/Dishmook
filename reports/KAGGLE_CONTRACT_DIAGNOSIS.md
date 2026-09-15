# First real GPU evaluation: user-reported evidence

The user pasted results from Qwen2.5-7B-Instruct at revision a09a35458c702b33eeacc393d103063234e8bc28, NF4/CUDA, seed 7, 12 known-answer cases, 2048 output tokens per campaign. These logs were produced in the user's Kaggle session; the developer did not independently run the GPU experiment or receive its full archive.

Original code: 683f2aaf71b413c354638dc1c84e21b5fcf49af6. Original protocol SHA: 9d0ee7a355eaa584f3ca12779bc929194b3b3deb58472181d21a83206fefd613.

Five accepted answers passed numeric/exact/AST assessment; seven campaigns failed parsing. End-to-end accuracy and schema acceptance were both 5/12. The seven failures were energy, period, dimensions, limit, probability, code, uncertainty. Raw pasted outputs identify two contract violations: object-valued disagreements where strings are required, and unescaped LaTeX backslashes in JSON strings. Some answers appear correct on inspection, but the original scores must not be retrospectively promoted. Reasoning and citations were not validated. Accepted cases included three invalid citation IDs.

The user also observed 12 leaked-semaphore warnings at process shutdown. The worker previously terminated even idle children; allowing EOF and bounded graceful exit is a plausible remediation, not yet confirmed on Kaggle.

Changes: clarify field types and plain-text math, forbid invented citation IDs and irrelevant disagreements in the prompt, preserve strict parsing, report completed_with_failures/nonzero exit for failed campaigns, distinguish accepted-answer accuracy from end-to-end accuracy, and allow five seconds for idle worker cleanup before termination. This is not constrained decoding and does not guarantee valid model output.

Experiment protocol version is now 2. Use a NEW output directory for the revised prompt. Old reports and checkpoint archives remain unchanged. Do not resume an old campaign with a revised prompt implementation. First rerun the seven failed cases as a diagnostic subset, then evaluate all 12 cases under the same revised protocol before any model/agent comparison. The subset is selected from observed failures and is not an unbiased new benchmark.
