# Security boundary

Problem statements and document strings are untrusted data. Phase 0 hashes fixture input; it never evaluates code, fetches documents, invokes subprocess tools or opens paths supplied by a model. The fixed response does not echo input. CLI validation errors omit Pydantic's input values.

Identifiers reject path separators and traversal forms, but this is not a filesystem sandbox. The network-disabled policy is a configuration constraint. Test socket patches detect ordinary Python network access; they are not operating-system isolation.

Before generated-code execution is introduced, implement and test an actual isolated runtime with time and memory limits, denied network, allowlisted libraries and no inherited credentials. Do not claim a Python subprocess alone is secure isolation. Before document retrieval, address prompt injection, provenance spoofing and sensitive data redaction. Never commit keys or private research inputs.
