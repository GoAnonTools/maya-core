# Maya Remote Deployment V1

## 1. Purpose

This document defines the future remote deployment architecture for Maya. It
describes how client applications connect to a server-side Maya Core, which
in turn coordinates Lightning and the Hermes runtime.

This is an architecture specification only. It does not introduce an
implementation, deployment manifests, network endpoints, or runtime changes.

## 2. Architecture

### Client devices

Maya clients may include:

- Maya UI desktop;
- future mobile clients;
- future web clients.

Clients provide the user-facing interaction surface. They authenticate the
user with the Maya Core server and submit requests through the Maya client
protocol. Clients do not connect directly to Lightning or Hermes.

### Server

The server deployment contains:

- Maya Core;
- Lightning service;
- Hermes runtime.

The logical topology is:

```text
Maya UI desktop
Future mobile/web clients
          |
          v
    Maya Core server
          |
          v
    Lightning service
          |
          v
     Hermes runtime
```

Maya Core is the client-facing orchestration boundary. Lightning is the
adapter and transport boundary for delegated work. Hermes is the specialist
execution backend. The server may run these components as separate processes,
services, or future containers while preserving the same logical boundaries.

## 3. Service boundaries

### Maya clients

Clients own presentation, user interaction, local session state needed for
the interface, and display of Maya Core responses and delegation progress.
They must not own routing policy, specialist selection, permission decisions,
or direct Hermes credentials.

### Maya Core server

Maya Core owns:

- user identity and session association;
- request normalization;
- routing and task classification;
- permission and approval policy;
- delegation lifecycle;
- memory and context policy;
- the client-visible API and event stream.

Maya Core is the authority for all work initiated by clients. It decides
whether a task is delegated and what context and permissions are passed to
the downstream services.

### Lightning service

Lightning owns the server-side connection to Hermes and the conversion between
Maya delegation jobs and Hermes worker jobs. It manages worker transport,
connection state, job lifecycle conversion, event forwarding, correlation, and
transport failures.

Lightning must not become a second client API, bypass Maya Core policy, or
accept unsolicited user work.

### Hermes runtime

Hermes owns specialist execution, agent reasoning, plugins, and specialist
tools. It receives only authorized jobs from Lightning and must operate within
the task scope, capabilities, context, workspace, and permissions supplied by
Maya Core.

Hermes is an internal server component. It is not directly addressable by
clients or exposed as a public user-facing service.

## 4. Network communication

The expected communication paths are:

```text
Client <---- authenticated client protocol ----> Maya Core
Maya Core <---- internal service protocol ----> Lightning
Lightning <---- worker transport ----> Hermes
```

The client-to-Maya Core connection carries authenticated user requests,
responses, delegation state, progress events, approval interactions, and
errors. It may support request/response traffic plus a streaming channel for
server events.

The Maya Core-to-Lightning connection carries explicit delegation requests,
policy-bound execution context, lifecycle commands, cancellation, approval
state, and normalized events.

The Lightning-to-Hermes connection carries Hermes-specific jobs and worker
events. Its transport is an implementation detail behind Lightning and must
not leak into the client protocol.

All production network communication must use encrypted transport. Internal
service traffic must be authenticated and authorized even when the services
run on a private network. Network placement alone is not a sufficient trust
boundary.

## 5. Authentication and authorization requirements

The remote deployment must provide:

- authenticated client users;
- authenticated service-to-service connections;
- authorization checks at the Maya Core boundary;
- scoped credentials for Lightning and Hermes;
- session and delegation correlation;
- revocation and expiration handling;
- audit records for security-relevant actions.

Maya Core must establish the user identity before accepting a client request
and must evaluate authorization before creating a delegation. User credentials
must not be forwarded to Hermes unless an explicit, narrowly scoped policy
requires it.

Lightning must authenticate to Hermes as a service, not impersonate an
arbitrary user. Hermes must accept jobs only from an authorized Lightning
identity and must reject direct or unauthenticated job submission.

Authentication failures, expired credentials, revoked sessions, and lost
service authorization must fail closed and produce observable errors without
exposing secrets.

## 6. Configuration separation

Configuration is separated by ownership and trust boundary.

### Client configuration

Client configuration contains the Maya Core server address, client display
settings, and non-secret feature settings. It must not contain Hermes
credentials, internal service addresses, or server-side permission policy.

### Maya Core configuration

Maya Core configuration contains user/session integration, routing policy,
memory and context policy, approval policy, server listeners, and the
authorized Lightning service identity or connection settings.

### Lightning configuration

Lightning configuration contains Hermes endpoint and transport settings,
worker registration behavior, connection timeouts, retry policy, and scoped
service credentials. It must not redefine Maya routing or grant permissions
that Maya Core has not supplied.

### Hermes configuration

Hermes configuration contains runtime, profile, plugin, and specialist-tool
settings. It must not contain client-facing identity policy or override the
permissions and task scope received from Maya Core.

Secrets should be supplied through an appropriate secret-management mechanism
in production. They must not be embedded in client bundles, committed to the
repository, or included in ordinary logs and event payloads.

## 7. Local development mode

Local development mode is intended for development and integration work. All
components may run on one machine:

```text
Maya UI desktop
      |
      v
Maya Core + Lightning service + Hermes runtime
```

The components may use local process communication or loopback network
connections, but the logical service boundaries and authorization checks
should remain visible. Development configuration may use local credentials,
mock identities, and local worker profiles, provided these are clearly
separated from production configuration and cannot be mistaken for production
secrets.

Local mode must still exercise the delegation boundary and should preserve
the same client-to-Core and Core-to-worker contracts expected in remote mode.

## 8. Production mode

Production mode separates the client-facing Maya Core server from the
internal execution services:

```text
Client devices
      |
      v
Maya Core server
      |
      v
Lightning service
      |
      v
Hermes runtime / worker pool
```

The public network boundary terminates at the Maya Core client interface.
Lightning and Hermes should remain on protected server networks or otherwise
be restricted to authenticated service-to-service access.

Production operation should include health monitoring, structured logs,
correlated request and delegation identifiers, bounded retries, graceful
cancellation, backup and recovery procedures for required state, and a clear
upgrade strategy for each service.

## 9. Security considerations

The deployment must account for:

- encrypted transport between clients and services;
- authenticated and authorized service-to-service communication;
- least-privilege service accounts;
- isolation of Hermes workspaces and credentials;
- strict separation of client, internal, and administrative interfaces;
- input validation and request-size limits at Maya Core;
- rate limiting and abuse protection for client access;
- safe handling of streamed events and tool output;
- secret redaction in logs, errors, and telemetry;
- session expiration, revocation, and cancellation;
- auditability of delegations, approvals, and privileged operations;
- resource limits for Hermes plugins and specialist tools.

Hermes must not gain unrestricted machine access merely because it is hosted
on the same server as Maya Core. Remote deployment changes the placement of
components, not the authority model: Maya Core remains responsible for
routing, permissions, and delegation lifecycle.

## 10. Future container deployment

The architecture is intended to support future container deployment without
changing the service responsibilities:

```text
Client network
      |
      v
Maya Core container
      |
      v
Lightning container
      |
      v
Hermes container(s)
```

Containers may be scheduled independently to scale Maya Core, Lightning, or
Hermes workers according to their different workloads. Container networking,
service discovery, secrets, volumes, resource limits, and health checks must
preserve the same authentication and authorization boundaries described above.

Containerization must not be treated as a security boundary by itself. Each
service still requires explicit credentials, restricted network access,
least-privilege execution, and bounded access to files, tools, and external
resources.

No container manifests, orchestration configuration, or runtime integration
are defined by this document.
