# Maya Lightning Worker V1

## 1. Purpose

Lightning is Maya's specialist execution platform. It provides an execution
layer for delegated work that is better handled by focused specialist agents
than by Maya's primary conversational worker.

Maya Core remains the client-facing orchestration boundary. It owns request
normalization, policy, routing, permissions, delegation, and the canonical
protocol. Lightning receives explicitly delegated work from Maya Core and
returns structured lifecycle events.

Lightning is not a model provider. It is an execution layer that manages
specialist workers. A specialist may use one or more models internally, but
that implementation detail is behind the Lightning Worker protocol.

## 2. Architecture

```text
Maya Core
    |
    v
Delegation Manager
    |
    v
Lightning Worker Platform
    |
    +--> Coding Specialist
    +--> Research Specialist
    +--> Future specialists
```

Maya Core decides whether work should be delegated and creates a provider-
neutral delegation request. The Delegation Manager owns the delegation
lifecycle. Lightning executes the delegated task through an appropriate
specialist worker and emits structured events back through the manager.

The boundary is intentionally transport-independent. Lightning may be hosted
in the same process, as a local service, or remotely without changing the
Maya Core delegation contract.

## 3. Worker model

Every worker exposes descriptive metadata before it is used for execution.

### Worker identity

A worker has a stable `worker_id` and a human-readable display name. The ID is
used in capability registration, delegation decisions, event correlation, and
observability. Worker identity must not be inferred from a model name or a
transport endpoint.

### Worker capabilities

Capabilities are provider-neutral strings describing what a worker can do.
Examples include:

- `coding`
- `research`
- `tool_call_proposal`
- `filesystem_read`

Required capabilities are included in delegation requests. A worker may be
selected only when its advertised capabilities satisfy the request.

### Worker roles

Workers advertise a high-level role, such as:

- `conversational`
- `specialist`
- `fallback`

The role describes responsibility, not implementation technology.

### Worker availability

Availability indicates whether the worker is currently eligible for
execution. A capability record may exist while its worker is unavailable or
not yet registered as executable. Unavailable workers must fail or be skipped
according to Maya Core policy; they must not be invoked implicitly.

### Worker metadata

Metadata may include display information, execution mode, workspace scope,
supported event features, permissions, and other descriptive values needed by
future policy. Metadata must not grant permissions or override the Maya
contract.

## 4. Delegation lifecycle

Delegated work progresses through explicit, observable states:

```text
created
   -> accepted
   -> started
   -> progress* 
   -> completed
```

The lifecycle may branch into approval, tool, failure, or cancellation paths:

```text
created -> accepted -> started -> progress
                              |       |
                              |       +--> approval_required -> progress
                              |                              |
                              |                              +--> cancelled
                              |
                              +--> tool_request -> progress
                              |
                              +--> completed
                              +--> failed
                              +--> cancelled
```

The states are:

- `created` — Maya Core has formed a delegation request.
- `accepted` — the delegation layer has accepted and recorded the request.
- `started` — Lightning has assigned the request to a specialist execution
  session.
- `progress` — the specialist reports observable progress.
- `approval_required` — work is paused pending an explicit approval decision.
- `tool_request` — the specialist requests a tool or operation subject to
  policy and permissions.
- `completed` — the specialist finished successfully and returned a result.
- `failed` — execution stopped unsuccessfully with a structured error.
- `cancelled` — execution was stopped by cancellation or policy.

Events should include the delegation ID and, where available, request ID,
session ID, progress, message, result/error data, and relevant metadata.
Terminal states are `completed`, `failed`, and `cancelled`.

## 5. Workspace and permissions

### Workspace isolation

Every delegated task executes within an explicitly identified workspace.
Workspace identity is part of the delegation context and must not be inferred
from ambient process state.

Workers may access only the workspace granted to the delegation. A worker
must not discover or access other workspaces, Maya's private runtime state, or
unrelated credentials.

### Allowed operations

Operations are categorized as:

- `read` — inspect permitted files, data, or documents without changing them.
- `write` — create or modify files or other workspace state.
- `execute` — run code, commands, tests, or tools.
- `network` — access external services or the internet.

Each delegation must declare the operations it may use. A capability to
perform an operation does not itself authorize that operation for every task.

### Approval requirements

Read-only work may be allowed automatically when covered by policy. Mutating,
execution, and network operations require explicit approval unless a more
restrictive policy disallows them entirely.

Approval is a policy decision owned by Maya Core. Lightning may report
`approval_required`, but it must not approve work autonomously or treat a
missing response as approval.

### No unrestricted machine access

Lightning specialists must never receive unrestricted machine access. They
must operate with least privilege, explicit workspace scope, explicit
operation permissions, and bounded credentials. Credentials and secrets must
not be exposed through worker metadata or ordinary event payloads.

## 6. Specialist types

### Coding Specialist

The Coding Specialist handles software-oriented delegated tasks, including:

- repository analysis;
- code changes within an approved workspace;
- testing and validation;
- documentation updates.

Code execution, file writes, dependency installation, deployment, and network
access remain governed by the delegation's permissions and approval policy.

### Research Specialist

The Research Specialist handles information-oriented delegated tasks,
including:

- information gathering;
- document analysis;
- summarization.

Network access, private-document access, and external sharing remain governed
by workspace and permission policy.

## 7. Lightning responsibilities

Lightning should:

- execute explicitly delegated tasks;
- manage specialist worker sessions;
- emit structured lifecycle and progress events;
- respect workspace and operation permissions;
- pause for required approval;
- support cancellation and propagate cancellation to active work;
- report completion and failure without concealing partial progress.

Lightning should not:

- decide Maya routing;
- bypass Maya Core or accept work outside the delegation protocol;
- modify permissions or expand its own capabilities;
- access unavailable or unassigned workspaces;
- silently perform operations not present in the delegation context;
- expose credentials or unrestricted machine access to specialists.

Maya Core remains the authority for routing, delegation policy, approval, and
the client-visible contract.

## 8. Future integration

The Lightning Worker Platform may later run as:

- a local service;
- a remote server;
- a cloud instance;
- a container.

The protocol must remain transport-independent. HTTP, WebSocket, process
messaging, queues, or another transport may be used behind the transport
adapter, but those details must not leak into `LightningJob`, `LightningEvent`,
worker capability metadata, or Maya Core's delegation lifecycle.

Future deployments must preserve:

- stable delegation and request correlation IDs;
- explicit workspace and permission boundaries;
- structured lifecycle events;
- cancellation propagation;
- deterministic failure reporting;
- the separation between Maya Core policy and Lightning execution.
