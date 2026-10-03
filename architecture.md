# Maya Architecture
> Version 0.2.0 — 2026-10-03  
> Philosophy: **cloud-first, local-capable**  
> Change from 0.1: Oracle Cloud temporarily unavailable. Lightning AI is now the extensible hub.

---

## Core principle

Maya is not one program. Maya is a system.

| Layer | Role | Platform |
|-------|------|----------|
| Maya UI | The face | GoAnonTools/maya-ui |
| Maya Core | The traffic controller | FastAPI / Python |
| Agent OS | The hands | Any framework behind a consistent API |
| Hermes | The brain | Lightning AI |
| Memory | The memory | Lightning AI (Phase 1) → Oracle later |
| Kaggle | The laboratory | Kaggle sandbox |

---

## Current architecture (Phase 1)

```
                         YOU

              Maya UI  (GoAnonTools/maya-ui)
              (voice + interface)
                         |
                  Maya Core Router
                         |
        ------------------------------------------------
        |                                              |
   Maya Daily                                     Maya Lab
   (trusted)                                      (sandbox)
        |                                              |
   Lightning AI                                    Kaggle
        |                                              |
   Hermes                                          DeerFlow
   Memory                                          Coding models
   API                                             Experiments
        |
        |
        +----------- EXTENSIBLE HUB -----------+
                          |
          --------------------------------
          |              |               |
      Lightning 2      Oracle          Other VPS
          |              |               |
   Specialist AI     Long-term       Future services
   Vision/Coding     memory          APIs
   (future)          (when ready)    (future)
```

---

## Routing logic

```
Request arrives at Maya Core
          |
          ↓
Internet + Lightning available?
          |
          +-- YES --> Agent OS --> Hermes (full Maya)
          |                            |
          |                       Memory read/write
          |
          +-- NO  --> Local Qwen (offline, limited)
                      user notified immediately
```

---

## Memory strategy

```
Phase 1 (now):
  Lightning AI hosts Hermes + memory service
  Simple SQLite or file-based storage
  Maya Core talks to a /memory API endpoint

Phase 2 (when Oracle available):
  Swap memory endpoint URL in Maya Core config
  No Core rewrite — just one config change
  Oracle becomes long-term persistent store

Future:
  Multiple backends possible
  Lightning 2 = specialist models (vision, coding)
  Other VPS = future APIs and services
```

**Key design rule:** Maya Core never talks directly to a database.  
It always talks to a `/memory` API. The backend behind that API can change freely.

---

## Agent OS interface principle

```
Maya Core
    |
    | HTTP / OpenAI-compatible API
    |
Agent OS endpoint
    |
[AutoGen | CrewAI | LangGraph | anything else]
```

Maya Core never imports or depends on an agent framework directly.  
It calls an API. The framework behind that API is an implementation detail.  
Swapping frameworks = swapping one service. Zero Maya Core changes.

The Agent OS must expose:
- `POST /task` — submit a task with context
- `GET /task/{id}` — check task status
- `GET /task/{id}/result` — retrieve result

That contract is what matters. Not the framework.

---

## Environment rules

### Maya Daily (production)
- Trust: high
- Memory: persistent (Lightning AI Phase 1, Oracle later)
- Permissions: limited, contract-enforced
- Default mode: 95% of usage

### Maya Lab (sandbox)
- Trust: temporary
- Memory: disposable (Kaggle session only)
- Permissions: high (install, run, modify, experiment)
- Triggered by: explicit delegation from Maya Daily

### Isolation (never cross these lines)
- Lab → Daily: results only (PRs, reports) — never credentials
- Daily → Lab: tasks only — never private data
- Memory → Lab: never automatically — explicit request only
- Lab → Memory: never directly — requires Daily review + approval

---

## Infrastructure map

| Component | Platform | Status |
|-----------|----------|--------|
| Maya UI | GitHub / local | ✅ Existing: GoAnonTools/maya-ui |
| Maya Core | Local / VPS | 🔧 To build: maya-core repo |
| Agent OS | Any framework | 🔧 Expose via consistent API endpoint |
| Hermes | Lightning AI | 🔧 To deploy |
| Memory (Phase 1) | Lightning AI | 🔧 Simple storage alongside Hermes |
| Maya Lab | Kaggle | ✅ Account ready |
| Local fallback | User laptop | ✅ Qwen 2B/3B |
| Oracle VPS | Oracle Cloud | ⏸ Blocked — plug in later |

---

## Build phases

### Phase 0 — Prepare the workshop (today)
- [x] Architecture documented
- [x] maya-contract.yaml written
- [x] maya-identity.yaml written
- [ ] Lightning AI account + workspace ready
- [ ] Kaggle account verified
- [ ] Agent OS API contract defined (framework chosen later, independently)
- [ ] Model serving method chosen (vLLM vs Ollama)

### Phase 1 — Working conversation
Goal: `Maya UI → Maya Core → Hermes` connected and talking  
No memory, no tools, no agents yet. Just a working chat.

### Phase 2 — Identity
Goal: `maya-identity.yaml` injected into every request  
Maya feels like Maya on both Hermes and Qwen fallback.

### Phase 3 — Memory (Lightning AI)
Goal: Maya remembers projects, preferences, decisions  
Stack: simple storage on Lightning AI, behind a `/memory` API

### Phase 4 — Agent OS
Goal: Maya can delegate multi-step tasks

### Phase 5 — Maya Lab
Goal: `Maya Daily → task → Kaggle → DeerFlow → PR → user review`

### Phase 6 — Oracle (when available)
Goal: Swap memory backend to Oracle VPS  
One config line change. No Core rewrite.

---

## Decisions log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-10-03 | Cloud-first, not local-first | Reliability over raw control |
| 2026-10-03 | Qwen is fallback only | Hermes reasoning is significantly better |
| 2026-10-03 | Personality lives in identity file, not in model | Model-agnostic — swap models without changing Maya |
| 2026-10-03 | Lab and Daily are isolated environments | Security: Lab never touches production data |
| 2026-10-03 | Contract written before code | Prevents permission creep over time |
| 2026-10-03 | Oracle removed from Phase 1 | Access blocked — not worth delaying start |
| 2026-10-03 | Lightning AI becomes extensible hub | Hosts Hermes + memory now, other backends plug in later |
| 2026-10-03 | Memory behind API endpoint | Backend can change without touching Maya Core |
| 2026-10-03 | Agent OS framework not hardcoded | Maya Core talks to an API contract, not a framework — swap freely |
