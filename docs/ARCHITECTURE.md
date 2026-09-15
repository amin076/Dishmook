# Architecture

The Phase 0 CLI constructs a fixture Problem, Agent, Task and Run. The Fake Backend validates entity references and returns one unverified Claim. Output goes to stdout as JSON; the CLI does not write run state.

`domain.py` owns contracts and their invariants. `inference.py` owns the deterministic fixture. `cli.py` owns argument parsing and JSON presentation. No domain class calls a service.

Future direction from the specification: one shared open-weight model, small scheduler, bounded logical agents, evidence storage, independent verification and comparative evaluation. None of these future components should be inferred from the Phase 0 smoke result.
