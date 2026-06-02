# Multi-Provider Role Dispatch — Design Notes

Internal notes for developers on the role candidate schema, selector
state, and dispatch ordering introduced by the TASK-407 epic.

## Overview

Each dispatch **role** (fast / standard / deep / default) maps to an
ordered list of `(provider_id, model)` **candidates**. The orchestrator
tries candidates in priority order; the first to pass the availability
preflight and start successfully handles the task. This enables failover,
redundancy, and load-spreading without changing the agent-profile model.

## Data model

```
RoleStore (.oompah/roles.json)
  └── Role
        ├── name: str          # "fast", "standard", "deep", "default"
        ├── strategy: str      # "priority" | "round_robin"
        ├── candidates: list[Candidate]
        └── updated_at: datetime

      Candidate
        ├── provider_id: str
        └── model: str
```

`Role.provider_id` and `Role.model` are backward-compat properties that
delegate to `candidates[0]`. Callers that access them continue to work
without modification.

### Serialization

New format (written by `Role.to_dict()`):

```json
{
  "name": "fast",
  "strategy": "priority",
  "candidates": [
    { "provider_id": "prov-abc", "model": "gpt-4o" },
    { "provider_id": "prov-def", "model": "claude-3-5" }
  ],
  "updated_at": "2026-01-01T12:00:00+00:00"
}
```

Legacy format (read by `Role.from_dict()` for backward compat):

```json
{ "name": "fast", "provider_id": "prov-abc", "model": "gpt-4o", "updated_at": "..." }
```

Legacy entries are promoted to one-candidate priority roles in memory.
Saves always write the new multi-candidate format.

## CandidateSelector — selector state

```
CandidateSelector (.oompah/role_usage.json)
  └── usage: dict
        └── role_name → provider_id → model → last_used_at (ISO str)
```

The selector is a **read side-effect** of each dispatch. It is the only
object that knows "which candidate was used most recently for a given
role."

### ordered_candidates(role)

Returns the candidates in dispatch order without writing anything to
disk.

- **priority**: returns `role.candidates` as-is (configured order).
- **round_robin**: sorts candidates by `last_used_at` ascending; never-
  used candidates (`None`) sort before any used one; ties broken by
  configured index.

### record_used(role_name, candidate)

Called by `Orchestrator._run_worker` after a candidate starts
successfully (not just after the task finishes — the goal is to
prevent repeated hammering of the same provider):

```python
self._candidate_selector.record_used(target.role_name, target.candidate)
```

`record_used` does **not** run inside the orchestrator lock. It has its
own in-process `threading.Lock` and writes to `role_usage.json`
independently of `roles.json`.

### Key properties

- **Separate state file**: usage state lives in `role_usage.json`, not
  `roles.json`. Editing roles never resets usage; usage records for
  removed candidates are silently ignored.
- **No server dependency**: `CandidateSelector` can be instantiated and
  tested without a running HTTP server.
- **Concurrent-safe**: `threading.Lock` guards the in-process dict and
  file writes, so multiple coroutines dispatching concurrently do not
  race.
- **Provider Test button**: does not call `record_used`. Only real
  dispatches update usage state.

## DispatchTarget

`DispatchTarget` is a dataclass produced by
`Orchestrator._resolve_dispatch_targets()` and consumed by
`Orchestrator._run_worker()`:

```python
@dataclass
class DispatchTarget:
    role_name: str
    provider: ModelProvider
    model: str | None
    candidate_key: str   # "provider_id/model" — used in logs and error messages
    source: str          # "role:fast[0]" — human-readable origin for tracing
    candidate: Candidate | None  # used by record_used; None for non-role targets
```

`_resolve_dispatch_targets` asks `CandidateSelector.ordered_candidates()`
for the ordered candidate list and turns each into a `DispatchTarget`.

## Dispatch loop

```
_run_worker(issue, attempt, profile)
  ↓
targets = _resolve_dispatch_targets(profile)   # [DispatchTarget, ...]
  ↓
for target in targets:
    reason = _candidate_preflight(target)      # "" → usable; non-empty → skip
    if reason:
        skip_reasons.append(...)
        continue
    try:
        await _run_api_worker / _run_acp_worker(...)   # may raise ProviderStartupError
        record_used(target.role_name, target.candidate)
        return   # success
    except ProviderStartupError as e:
        skip_reasons.append(...)
        continue  # try next candidate
  ↓
# All candidates failed → _on_worker_exit("abnormal", error_msg)
```

### Preflight checks (in order)

1. **rate_limited** — active cooldown from a recent 429 (`_is_rate_limited()`)
2. **missing_credentials** — non-ACP provider with empty `api_key`
3. **budget_exceeded** — spend limit reached and model is not free-tier
   and provider is not ACP-subscription-billed
4. **invalid_model** — model not in provider catalog (and not ACP
   empty-catalog)

Startup errors raised after the preflight (inside `_run_api_worker` or
`_run_acp_worker` before the agent begins turns) are caught as
`ProviderStartupError` and cause the same fallthrough-to-next-candidate
behaviour.

## Backward compatibility

| Old code path | New behaviour |
|---|---|
| `role.provider_id` / `role.model` | Properties that delegate to `candidates[0]`; unchanged |
| `PUT /api/v1/roles` legacy body (`{provider_id, model}`) | Promoted to one-candidate priority role; response includes `strategy` + `candidates` |
| `roles.json` with flat `provider_id` / `model` | Read as one-candidate priority role; rewritten in new format on next save |
| Single-candidate dispatch | `_resolve_dispatch_targets` returns a one-element list; same code path; no regression |

## File locations

| File | Purpose |
|------|---------|
| `oompah/roles.py` | `RoleStore`, `Role`, `Candidate`, `CandidateSelector`, migration helper |
| `oompah/orchestrator.py` | `DispatchTarget`, `_resolve_dispatch_targets`, `_candidate_preflight`, `_run_worker` |
| `oompah/server.py` | `GET /api/v1/roles`, `PUT /api/v1/roles`, `POST /api/v1/providers/{id}/test` |
| `.oompah/roles.json` | Persisted role → strategy + candidates mapping |
| `.oompah/role_usage.json` | Persisted per-candidate last-used timestamps |

## Related plans

- `plans/acp-backends.md` — ACP provider mode and SDK selection
- `plans/per-focus-models.md` — how focus labels interact with model roles
- `plans/submit-queue.md` — dispatch concurrency context
