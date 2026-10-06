# Maya Local Services Configuration V1

## 1. Purpose

This document defines the local multi-service configuration boundary for Maya.
It prepares the current laptop architecture for a future remote service
architecture while preserving current runtime behavior.

This is documentation and configuration-boundary preparation only. It does
not add deployment, Docker configuration, Hermes integration, routing
changes, API changes, or UI changes.

## 2. Current local architecture

The intended local service boundary is:

```text
Maya UI
    |
    v
Maya Core
    |
    v
Lightning service
    |
    v
Future Hermes service
```

The current repository provides the Maya Core application and Lightning
protocol/service placeholders. Hermes is a future service boundary and is not
implemented by this configuration specification. The current laptop mode may
keep the components local or in-process while retaining these logical
ownership boundaries.

Maya Core remains responsible for identity, configuration loading, routing,
permissions, context, and delegation policy. Lightning remains responsible
for its worker/service boundary. A future Hermes service must remain behind
Lightning and must not become a direct client dependency.

## 3. Current configuration handling

The current configuration sources are:

- `configs/maya-config.yaml` for local Maya mode and service settings;
- `configs/maya-identity.yaml` for Maya identity and prompt configuration;
- `configs/maya-contract.yaml` for contract, environment, memory, permission,
  and tool policy;
- environment variables for selected worker connection and model settings;
- application defaults for values such as the default Ministral model.

`app/config.py` currently resolves the configuration directory relative to the
repository and defines the YAML paths. `app/settings.py` loads
`maya-config.yaml` and exposes only selected non-sensitive values through the
public settings view.

The current local service configuration includes a model service with a
localhost base URL, Lightning worker configuration placeholders, and an
optional Ministral route. These values describe the current laptop setup;
they are not a remote deployment implementation.

Future work may replace fixed local values with independently supplied
configuration, but this document does not change the existing loading or
runtime behavior.

## 4. Configuration principles

### Independent service configuration

Each service must be configurable independently. A Maya Core URL, Lightning
service URL, and future Hermes service URL must have separate ownership and
configuration entries. Changing one service location must not require changing
routing logic, APIs, or UI code.

### No hardcoded localhost dependency

Localhost values must be configuration values, not assumptions embedded in
service behavior. Local development may continue to use `localhost` or
`127.0.0.1`, but those values must be replaceable through configuration when
services move to another host.

### Remote URL substitution

Future remote URLs should require only configuration changes. The service
boundary, request contracts, authentication hooks, and ownership rules must
remain stable when a local endpoint is replaced with a remote endpoint.

### Secrets outside source code

API keys, access tokens, signing keys, passwords, private certificates, and
other secrets must remain outside source code and committed configuration.
They should be supplied through environment variables, local secret files
excluded from version control, or a production secret-management mechanism.

Secrets must not be exposed through public configuration status, logs,
ordinary error messages, client bundles, or delegation metadata.

### Configuration is not authority

Configuration identifies endpoints and defaults; it does not grant authority
by itself. Maya Core permissions and approval policy remain the source of
truth for operations and delegation.

## 5. Configuration categories

The following categories define the future-ready boundary. They are
conceptual configuration ownership areas and do not require new runtime
fields in this version.

### Maya Core URL/configuration

Maya Core configuration should identify:

- the Maya Core bind address and port for local operation;
- the client-facing Maya Core base URL;
- Maya mode, such as local, online, or offline-capable mode;
- identity, contract, routing, memory, and context configuration sources;
- client session and server authentication placeholders;
- safe health and status behavior.

The client should depend on the configured Maya Core URL rather than knowing
where Lightning or Hermes runs. Maya Core configuration must not require the
client to connect directly to downstream services.

### Lightning service URL/configuration

Lightning configuration should identify:

- the Lightning service URL or local transport target;
- whether the Lightning boundary is enabled;
- worker or deployment identity;
- advertised capabilities;
- workspace scope;
- permitted operations;
- connection, timeout, retry, and health settings;
- service authentication placeholders.

The current code already has future-facing Lightning environment placeholders
such as `MAYA_LIGHTNING_ENDPOINT`, `MAYA_LIGHTNING_WORKSPACE`,
`MAYA_LIGHTNING_DEPLOYMENT`, `MAYA_LIGHTNING_CAPABILITIES`,
`MAYA_LIGHTNING_PERMISSIONS`, and `MAYA_LIGHTNING_ENABLED`. Their presence
does not create a network deployment; they describe the intended independent
configuration boundary.

### Hermes service placeholder

The configuration boundary should reserve a Hermes service category for:

- Hermes endpoint or local service target;
- enabled/available state;
- profile and capability metadata;
- worker identity;
- service authentication placeholder;
- workspace and resource policy references.

The Hermes category is a placeholder only. No Hermes client, transport,
profile registration, or integration is added by this document.

### Ministral API configuration

Ministral configuration should identify the configured OpenAI-compatible
service without embedding credentials:

- provider name;
- model name;
- base URL;
- optional endpoint override;
- online/availability mode;
- API-key or token reference supplied outside source code.

The current implementation reads Ministral values from `services.ministral`
when present and supports environment overrides such as
`MAYA_MINISTRAL_MODEL`, `MAYA_MINISTRAL_BASE_URL`, and
`MAYA_MINISTRAL_ENDPOINT`. These values should remain independent from the
Maya Core and Lightning service locations.

### Local fallback model configuration

Fallback model configuration should identify:

- the local model provider;
- model name or local model path;
- local endpoint, if the model is served through a local API;
- availability and offline mode;
- resource limits and workspace assumptions.

The fallback model is an execution option. It must not silently change routing
policy or bypass Maya Core permissions. Its configuration must remain
separate from remote Ministral and future Hermes settings.

### Workspace paths

Workspace configuration should identify:

- the permitted local workspace root;
- configuration and data directories;
- log directory;
- model or cache directories where applicable;
- temporary working directory;
- future remote workspace identity or mount reference.

Paths must be explicit and scoped. A service must not infer a broader machine
scope from its process working directory. Remote workspace identifiers should
be replaceable for local filesystem paths without changing policy semantics.

### Permissions

Permission configuration should describe:

- allowed operation categories, such as read, write, execute, and network;
- workspace scope;
- approval-required operations;
- environment or identity restrictions;
- service-level capability limits.

Permissions belong to Maya Core policy. Lightning and future Hermes
configuration may advertise capabilities or carry scoped permissions, but
must not expand the authority defined by Maya Core.

### Authentication placeholders

Authentication configuration should reserve separate placeholders for:

- Maya Core client authentication;
- Maya Core-to-Lightning service authentication;
- Lightning-to-Hermes service authentication;
- Ministral API authentication;
- future remote certificate or trust configuration.

The placeholders define ownership and separation only. They do not implement
authentication in this version. Local development credentials must be
obviously distinct from production credentials and must never be committed as
real secrets.

## 6. Development mode

In development mode, everything runs locally:

```text
localhost services
local logs
local development credentials
```

Maya UI, Maya Core, the Lightning service boundary, and future Hermes service
processes may use localhost endpoints or local process communication. Local
logs should remain on the development machine and include correlation data
without recording secrets.

Development credentials may be placeholders or locally generated credentials.
They are for local use only and must not be reused as production credentials.
Local mode should make endpoint and credential ownership visible so that a
remote URL can later replace a localhost value through configuration alone.

## 7. Future production mode

In a future production mode, services may move independently to:

- a remote server;
- containers;
- cloud infrastructure.

The logical relationship remains:

```text
Maya UI / future clients
          |
          v
     Maya Core
          |
          v
   Lightning service
          |
          v
   Future Hermes service
```

The move from local to remote must change service configuration, credentials,
and operational settings—not routing behavior, public APIs, or UI logic.
Maya Core should remain the client-facing authority, with Lightning and
Hermes protected as internal service boundaries.

Production configuration must use encrypted network transport, real
service-to-service authentication, managed secrets, restricted workspace
paths, explicit permissions, and separate logs and observability settings.

## 8. Non-goals and invariants

This preparation does not:

- add deployment;
- add Docker or container manifests;
- add Hermes integration;
- change routing behavior;
- change APIs;
- change UI behavior;
- add tests.

The invariants are:

- Maya Core remains the orchestrator;
- service locations are configuration concerns;
- secrets remain outside source code;
- local mode remains supported;
- future remote placement does not require a change to the client-facing
  architecture.
