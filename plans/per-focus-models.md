# Plan: Per-Focus Model Selection

Today, the model used for an issue is determined entirely by the **agent
profile**: the orchestrator picks a profile from `WORKFLOW.md` based on the
issue's type/keywords/priority, then resolves the model via
`profile.model_role` against the provider's `model_roles`. The **focus** is
chosen independently and only shapes the prompt.

This plan adds the ability to bind a model (and optionally a provider) to a
**focus**, so foci like `docs` or `ui-architect` can run on a specific model
regardless of which profile happened to win profile matching.

---

## Goals

- Let users say "the `docs` focus always uses model X" without having to
  craft a parallel agent profile that mirrors the focus's matching rules.
- Keep profile-based model selection as the default. Focus-level overrides
  are opt-in and additive.
- Remain backward-compatible: existing `foci.json` files continue to work.
- Surface the override in the same places focus is already surfaced
  (dashboard, logs, cost telemetry).

## Non-goals

- Replacing the profile system. Profiles still drive matching, escalation,
  cost tracking, and turn limits.
- Cross-provider escalation logic for foci. Escalation continues to walk the
  profile hierarchy (`_PROFILE_HIERARCHY` in `orchestrator.py:1545`); the
  focus override applies to the *currently selected* profile, including
  escalated ones.

---

## Design

### 1. Extend the `Focus` dataclass

`oompah/focus.py:27-69` — add three optional fields and round-trip them in
`to_dict` / `from_dict`:

```python
model_role: str | None = None     # e.g. "deep" — looked up in provider.model_roles
model: str | None = None          # explicit model name override
provider_id: str | None = None    # pin a specific provider for this focus
```

All three are optional. When all three are `None`, behavior is identical to
today.

### 2. Resolution priority

When dispatching, the orchestrator already calls `_resolve_provider(profile)`
and `_resolve_model(profile, provider)`
(`oompah/orchestrator.py:1570-1583`). Introduce focus-aware variants that
take the selected focus and apply this priority:

```
provider:  focus.provider_id > profile.provider_id > default provider
model:     focus.model > focus.model_role(provider) > profile.model > profile.model_role(provider) > provider.default_model
```

Implementation: change `_resolve_provider` / `_resolve_model` to accept
`focus: Focus | None = None`, or wrap them in a single
`_resolve_provider_and_model(profile, focus)` that returns `(provider,
model)`. Prefer the wrapper — it's the only call site that needs both, and
it keeps the override logic in one place.

### 3. Wire focus into the worker

The worker selects focus *after* profile resolution
(`oompah/orchestrator.py:1748`), but model resolution happens *before*
focus selection (`:1723`). Reorder so focus selection runs first inside
`_run_api_worker` (or hoist it to `_run_worker` so the API/CLI paths share
it), then call the new resolver.

Validation (model role exists on provider, model is in `provider.models`)
already lives in `_run_api_worker:1726-1733`. Extend the error messages to
mention the focus name when the override is the source of the failure.

### 4. CLI agent path

`_run_cli_worker` (referenced from `:1715`) does not use providers/models the
same way. Audit its model resolution path; if it inherits from the profile,
add the same focus override there. If CLI agents don't take a model at all,
document that focus-level model overrides are API-agent only and log a
warning when a CLI-bound focus has overrides set.

### 5. Persistence and migration

- `.oompah/foci.json` — additive; existing files load with `None` defaults.
- Built-in foci library (`oompah/focus.py:91-`) — leave defaults at `None`
  so the out-of-box behavior is unchanged.
- No migration script needed.

### 6. Configuration UX

Foci are user-edited via:

- The `/foci` dashboard page (`oompah/templates/foci.html` + the API at
  `oompah/server.py:1100-1228`). Add three fields to the editor: a
  provider dropdown (populated from `/api/v1/providers`), a model-role text
  input, and an explicit-model text input. Make the model-role input a
  datalist sourced from the selected provider's `model_roles` keys.
- Direct `.oompah/foci.json` edits.

The PATCH endpoint (`server.py:1168`) needs to accept the new fields.

### 7. Telemetry and display

- `RunningEntry` already records `focus_name` / `focus_role`
  (`orchestrator.py:1782-1783`). Cost is tracked per profile
  (`models.py:274`). For per-focus visibility, also record `focus_name` on
  cost samples and add a `cost_by_focus` mirror of `cost_by_profile`.
  Optional but cheap — same change set.
- Log the resolved (provider, model, source) tuple at dispatch time, where
  source is `"focus"`, `"profile"`, or `"default"`. Useful when debugging
  why an issue ran on an unexpected model.

### 8. Validation rules

- A focus may set `model` xor `model_role`. If both are set, `model` wins
  and a warning is logged on load.
- A focus's `provider_id` must exist in the provider store at dispatch
  time. If missing, fall back to the profile's provider and log a warning
  (do not fail dispatch — provider rotation shouldn't strand work).
- A focus's `model_role` must be defined on the resolved provider. If
  missing, fall back to the profile's model and log a warning.

The "warn and fall back" stance matches the existing tolerance for
half-configured providers and avoids deadlocking the queue on a typo.

---

## Files to touch

| File | Change |
|------|--------|
| `oompah/focus.py` | Add fields to `Focus`, update `to_dict`/`from_dict`, update built-in defaults (no overrides set) |
| `oompah/orchestrator.py` | Add focus-aware provider/model resolver; reorder focus selection before model resolution; update validation error messages; optional `cost_by_focus` |
| `oompah/server.py` | Accept new fields in POST/PATCH `/api/v1/foci` |
| `oompah/templates/foci.html` | Editor inputs for provider/model_role/model |
| `tests/test_focus.py` | Round-trip new fields; validation rules |
| `tests/test_orchestrator_handlers.py` | Resolution priority (focus override > profile); fall-back-on-missing behavior |
| `README.md` | Document the new focus fields under "Focus system" |
| `WORKFLOW.md` template / `.env.example` | No changes (foci live in `.oompah/foci.json`) |

## Test plan

1. **Round-trip:** load a `foci.json` with the new fields, save it, diff is
   stable.
2. **Resolution priority:** parametrized test over the matrix
   `(focus.provider_id, focus.model, focus.model_role, profile.*)` asserting
   the final `(provider, model)`.
3. **Missing provider id on focus:** logs warning, falls back to profile
   provider, dispatch succeeds.
4. **Missing model_role on provider:** logs warning, falls back to
   profile-level model, dispatch succeeds.
5. **Backward compat:** an existing `foci.json` with no override fields
   produces identical resolution to today.
6. **API:** `PATCH /api/v1/foci/{name}` accepts new fields and persists.

## Rollout

- Single PR is fine — the change is additive and gated by the new optional
  fields. No flag needed.
- Document in the README with one example: `docs` focus pinned to a
  cheaper/faster model.

## Open questions

1. **CLI agent model overrides** — confirm whether CLI agents have a
   meaningful concept of "model" to override, or if focus-level model
   overrides should be silently ignored for CLI-bound work.
2. **Escalation interaction** — when a profile escalates from `standard` →
   `deep`, should the focus override still apply? Default yes (focus is
   orthogonal to profile tier), but worth a sanity check on real workloads.
3. **Per-role vs per-provider override** — the design lets a focus pin a
   *provider*. If a user wants "always Anthropic for `security` regardless
   of profile," `provider_id` covers it. We could also allow specifying a
   provider *role* (e.g. "any provider that has a `deep` role") but that
   adds complexity for a thin gain; defer until asked.
