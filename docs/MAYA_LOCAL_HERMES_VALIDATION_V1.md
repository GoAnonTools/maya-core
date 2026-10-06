# Maya Local Hermes Validation V1

This document describes the opt-in validation scenario for one real local
Hermes task. It does not enable production routing, register a worker, or
change the Maya UI.

## Enable local Hermes

Start a compatible local Hermes service, then configure Maya Core in the same
shell or service environment:

```text
MAYA_HERMES_ENABLED=true
MAYA_HERMES_ENDPOINT=http://127.0.0.1:8765/api
MAYA_HERMES_SMOKE_TEST=true
```

Run the opt-in validation test:

```bash
./.venv/bin/python -m unittest tests.test_hermes_local.HermesLocalSmokeTests
```

The scenario performs the following checks:

1. Loads and validates the local endpoint configuration.
2. Checks Hermes health.
3. Creates a safe, read-only research task.
4. Selects Hermes through the explicit opt-in selector.
5. Verifies the research capability.
6. Stops for Maya Core approval.
7. Approves the task through `DelegationManager`.
8. Submits the task and consumes Hermes SSE events.
9. Verifies completion and the persisted execution audit record.

## Environment variables

Required for the real scenario:

- `MAYA_HERMES_ENABLED=true` — explicit Hermes opt-in.
- `MAYA_HERMES_ENDPOINT` — absolute local Hermes HTTP(S) endpoint.
- `MAYA_HERMES_SMOKE_TEST=true` — explicit permission to perform a real
  endpoint smoke test.

Optional:

- `MAYA_HERMES_AUTH_TOKEN` — bearer token, when the local service requires
  authentication.
- `MAYA_HERMES_SUBMISSION_TIMEOUT` — submission timeout in seconds.
- `MAYA_HERMES_STREAM_TIMEOUT` — SSE stream timeout in seconds.
- `MAYA_HERMES_CANCELLATION_TIMEOUT` — cancellation timeout in seconds.
- `MAYA_HERMES_MAX_RECONNECTS` — maximum SSE reconnect attempts.

Configuration validation is local and does not contact Hermes. The smoke test
is the only scenario in this suite that uses a real endpoint; fake Hermes SSE
tests remain deterministic and continue to run without a Hermes installation.

## Disable Hermes

Disable the integration and prevent real smoke tests with:

```text
MAYA_HERMES_ENABLED=false
MAYA_HERMES_SMOKE_TEST=false
```

Alternatively, unset `MAYA_HERMES_ENDPOINT`. With Hermes disabled, the local
factory returns an unavailable Hermes executor and Maya continues using its
existing InMemory executor fallback. No routing or worker registration is
activated by this validation scenario.
