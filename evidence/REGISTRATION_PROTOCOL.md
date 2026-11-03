# Registration protocol for the confirmatory work packages

The pilot's predictions and their amendment are in `real-mcp/PREDICTIONS.md`, written before each run they concern; the guarded run's controllers are fixed in `real-mcp/results_guarded/manifest.json`, written before its first call. Every confirmatory experiment of WP1–WP3 follows these steps:

1. Fix the hypothesis, eligible population, selection rule, seed schedule, outcome grader, all arms with matched budgets, stopping rules, analysis code and missing-data policy before the treatment run.
2. Publish the digest of that package with an independent registry (OSF) or a witness signature from another researcher, and keep the timestamped record.
3. Freeze the controller and the feature extractor. The person who builds the hidden effects keeps implementations and triggers sealed from the controller author until the seal is recorded.
4. Grade unauthorized effects with an independent outcome grader that reads final state; benign but undeclared effects form their own class.
5. Run the controller behind the enforcing proxy (`runtime/mcp_proxy.py`): every decision and revision attestation is written to the hash-chained ledger before dispatch, and the chain heads go to the external witness during the run.
6. After unsealing, run the comparators — a static scanner, plain dynamic contract checks, MCPGuard-Dynamic and a per-tool policy baseline — under matched probe budgets and sensor access, and count both prevented harmful actions and held legitimate work.
7. Publish all trials, errors, exclusions, failed predictions and the registration record.
