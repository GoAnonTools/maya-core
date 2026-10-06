# Maya Hermes First Workload

This is the first production-style Hermes workload supported by the Maya
boundaries: a safe, read-only repository analysis.

The workload is opt-in and explicit. It does not change default routing,
register a worker, or add UI behavior.

## User task

```text
Analyze this project structure and provide recommendations.
```

The task is classified as a research workload and is marked read-only. Maya
Core still requires an approval decision before submitting it to Hermes.
Hermes cannot approve itself and no approval is inferred automatically.

## Execution flow

```text
Task creation
    |
    v
Maya policy recommendation: Hermes candidate
    |
    v
Hermes research capability check
    |
    v
WAITING_APPROVAL
    |
    v
Maya Core approval
    |
    v
Hermes submission and run_id mapping
    |
    v
SSE event forwarding
    |
    v
Final response and audit record
```

The audit record stores the selected executor, policy recommendation,
capability decision, approval state, lifecycle timestamps, final result, and
terminal status.

## Local validation

Configure and enable the local Hermes endpoint as described in
[MAYA_LOCAL_HERMES_VALIDATION_V1.md](MAYA_LOCAL_HERMES_VALIDATION_V1.md):

```text
MAYA_HERMES_ENABLED=true
MAYA_HERMES_ENDPOINT=http://127.0.0.1:8765/api
MAYA_HERMES_SMOKE_TEST=true
```

Run the real local validation suite:

```bash
./.venv/bin/python -m unittest tests.test_hermes_local.HermesLocalSmokeTests
```

The test verifies health, policy selection, capability validation, manual
approval, SSE completion, final result storage, and audit completion.

The deterministic first-workload test uses the fake Hermes SSE service and
always remains available without a Hermes installation:

```bash
./.venv/bin/python -m unittest tests.test_hermes_first_workload
```

## Dashboard repository analysis

The full Maya dashboard exposes **Analyze this repository** as an explicit
read-only capability. It is available only when Hermes is enabled with the
local configuration above. Maya Core creates the delegation, presents the
approval request, and starts Hermes only after the user approves it. No
automatic approval or write action is included.

The cross-boundary workflow contract is covered by:

```bash
./.venv/bin/python -m unittest tests.test_maya_hermes_user_workflow
```

## Disable Hermes

Set:

```text
MAYA_HERMES_ENABLED=false
MAYA_HERMES_SMOKE_TEST=false
```

Or unset `MAYA_HERMES_ENDPOINT`. The existing InMemory executor remains the
fallback, and no production routing path is enabled by this workload.
