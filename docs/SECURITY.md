# Security boundary

Problem statements and document strings are untrusted data in a user-role message. Agent configuration is operator-controlled instruction. Neither is executed as code. Prompt injection can still influence a model, so every candidate remains unverified and no generated tools run.

The only backends are fake and local Hugging Face. Local loading sets offline flags, disables telemetry, and requires local_files_only=True, trust_remote_code=False and safetensors. There is no remote inference client. These are application controls, not an OS network sandbox. Tests block Python socket connections; the actual-adapter CPU test generates local weights without downloads. The worker has a killable time boundary but no enforced OS memory cap. Future generated-code tools need separate memory/network/library isolation.

Strings are scrubbed for common token forms, password/key assignments and known secret environment values before persistence. Dependency output and raw exceptions are suppressed; only safe error codes are logged. Redaction is best-effort, not comprehensive. Never supply secrets. Run files contain research text and are not encrypted. They are ignored by Git and need review before sharing.

Run IDs reject traversal and separators. Existing IDs are not overwritten. Run directory, database, lock and export symlinks are rejected. An OS lock prevents concurrent controllers. Use a private trusted local filesystem; checks do not defend against hostile users concurrently replacing parent directories, SQLite sidecars or model files. Snapshots must be trusted, licensed and immutable during execution. Hashes verify integrity, not origin authenticity.

Model-generated verification/evidence fields are rejected. Only future independent validators may change scientific status.

Explicit `prepare-model --download` is a separate online provisioning step for pinned public snapshots. Inference remains local-only. Campaigns execute role prompts, never generated Python. Checkpoint ZIP restoration validates paths, types and expanded size; use trusted local directories and archive only closed runs.
