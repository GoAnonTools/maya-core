# Maya Hermes Integration V1

## 1. Purpose

Hermes is an execution backend for Maya. It provides specialist execution
capabilities behind Maya's orchestration and policy boundaries.

Maya Core remains the orchestrator and the authority for user-facing
behavior, routing, permissions, delegation, and context policy. Hermes does
not replace Maya Core and must not become a second orchestration layer.

Lightning is the adapter boundary between Maya and Hermes. It translates
Maya delegation requests into Hermes jobs, manages the worker transport and
job lifecycle conversion, and forwards Hermes events back to Maya Core.

## 2. Architecture

```text
Maya UI
    |
    v
Maya Core
    |
    v
Delegation Manager
    |
    v
Lightning Adapter
    |
    v
Hermes Runtime
```

Maya UI submits user requests to Maya Core. Maya Core classifies the task and
makes the routing decision. When delegation is appropriate, the Delegation
Manager creates and supervises the delegation lifecycle through the Lightning
Adapter. The adapter invokes Hermes and converts Hermes execution state and
events into the contract understood by Maya Core.

The boundary must remain transport-independent. Hermes may run in the same
process, on the local machine, or on a remote worker server without changing
Maya Core's orchestration responsibilities.

## 3. Responsibilities

### Maya Core

Maya Core owns:

- user identity;
- routing decisions;
- task classification;
- permissions;
- delegation lifecycle;
- memory and context policy.

Maya Core is the authority for whether a task is delegated, which specialist
profile is selected, what context is shared, which operations are allowed,
and whether approval is required. Hermes and Lightning must treat those
decisions as inputs rather than independently expanding them.

### Lightning Adapter

Lightning owns:

- worker transport;
- job lifecycle conversion;
- event forwarding;
- connection management.

Lightning converts Maya delegation requests to Hermes jobs and maps Hermes
acceptance, progress, completion, failure, cancellation, and approval-related
signals back into Maya's delegation lifecycle. It is responsible for
connection health, correlation identifiers, reconnection behavior, and
transport-level errors, but it does not make Maya routing or permission
decisions.

### Hermes Runtime

Hermes owns:

- specialist execution;
- agent reasoning;
- plugins;
- specialist tools.

Hermes is responsible for carrying out an authorized specialist job using the
selected profile and available plugins or tools. Its execution remains bound
by the task, context, capabilities, and permissions supplied through Maya and
Lightning.

## 4. Specialist mapping

Maya specialist types map to Hermes execution profiles as follows:

| Maya specialist | Hermes profile |
| --- | --- |
| Coding Specialist | Hermes coding profile |
| Research Specialist | Hermes research profile |

Future specialist categories include:

- documentation;
- data analysis;
- automation.

Future profiles must be registered and selected through Maya's capability and
routing policy. A Hermes profile must not be selected merely because it is
available; it must match the classified task and the permissions granted for
that delegation.

## 5. Security boundaries

Hermes must not:

- bypass Maya routing;
- access unrestricted machine resources;
- modify permissions;
- create unauthorized delegations;
- expose itself directly to users.

All Hermes work must originate from an authorized Maya delegation and pass
through the Lightning Adapter. Hermes receives only the identity, context,
capabilities, workspace scope, and operation permissions required for that
delegation. It must not infer additional authority from its local process,
host, plugins, tools, or network location.

Approval decisions remain owned by Maya Core. Lightning may carry approval
state and forward an approval request, while Hermes may pause execution or
report that approval is required. Neither layer may treat a missing or
ambiguous approval response as authorization.

Hermes is an internal execution component, not a client-facing endpoint.
Users interact with delegated Hermes work through Maya UI and Maya Core so
that identity, routing, permissions, lifecycle, and audit context remain
consistent.

## 6. Deployment models

### Local

Maya Core and Hermes run on the same machine:

```text
Maya UI
    |
    v
Maya Core + Lightning Adapter
    |
    v
Hermes Runtime
```

This model is suitable for low-latency execution and development. Local
placement does not remove the security boundaries or the requirement for
explicit delegation and permissions.

### Remote (preferred)

Maya remains the orchestration authority while Hermes runs on a worker
server:

```text
Maya UI/client
    |
    v
Maya Core server
    |
    v
Hermes worker server
```

The preferred remote model separates the client-facing orchestration plane
from the specialist execution plane. Lightning manages the authenticated
connection and lifecycle conversion between Maya Core and the Hermes worker
server.

### Hybrid

Lightweight workers may run locally while heavier workers run remotely:

```text
Maya UI
    |
    v
Maya Core + Lightning Adapter
    |                         |
    v                         v
Local lightweight workers    Remote heavy workers
```

Maya Core continues to make the routing decision. Worker location is an
execution constraint or capability, not an independent routing authority.

## 7. Future integration steps

The planned integration sequence is:

1. Implement the Lightning Adapter boundary for Hermes transport, request
   conversion, event forwarding, correlation, cancellation, and connection
   failure handling.
2. Register Hermes workers with stable identities, availability state, and
   advertised capabilities.
3. Define profile and capability mapping for Coding Specialist, Research
   Specialist, and future specialist categories.
4. Integrate the approval workflow so Maya Core remains the authority for
   operations that require explicit approval.
5. Add remote authentication, connection authorization, credential handling,
   and secure worker-server communication.

Each step must preserve Maya Core as the orchestrator and keep Hermes behind
the Lightning Adapter boundary. Deployment, transport, and Hermes-specific
execution details must not leak into Maya's user-facing routing or delegation
contract.
