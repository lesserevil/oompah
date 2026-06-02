# Multi-Provider Role Assignments

oompah supports assigning multiple provider/model **candidates** to each
dispatch role (fast, standard, deep, default). Candidates are tried in
order at dispatch time: the first one that passes availability checks and
starts successfully is used. If a candidate fails, the next one is tried
automatically.

## Concepts

### Roles

A **role** maps a logical tier name (e.g. `standard`) to one or more
provider/model candidates. The orchestrator resolves the role for each
dispatch and tries candidates in the order the role's strategy dictates.

The four standard roles are:

| Role | Typical use |
|------|-------------|
| `fast` | Chores, typo fixes, quick cleanup tasks |
| `standard` | The default tier for most issues |
| `deep` | Complex features, architectural changes |
| `default` | Catch-all for issues that don't match any profile |

### Candidates

A **candidate** is a `(provider_id, model)` pair. A role can have one
candidate (the original behaviour) or several. Each candidate is tried
in priority order; if the first fails, the second is attempted, and
so on.

### Strategies

Each role declares one of two **strategies**:

| Strategy | Behaviour |
|----------|-----------|
| `priority` | Always try candidates in the saved order. First candidate is the primary; subsequent candidates are fallbacks. |
| `round_robin` | Rotate through candidates so usage is spread evenly. The candidate that was used least recently is tried first. Never-used candidates sort before recently-used ones. Ties are broken by saved order. |

## Configuring multi-candidate roles

Open the **Providers** page (port 8090) and scroll to the Role Matrix
section.

### Setting the strategy

Each role shows two buttons: **Priority** and **Round-robin**. Click the
desired strategy button. The button turns active (darker background) to
confirm the selection.

### Adding a candidate

1. In the role's row, click **+ Add candidate**.
2. A new row appears with provider and model selectors.
3. Choose a provider and model from the dropdowns.

### Reordering candidates

Use the **↑** / **↓** buttons on each candidate row to change the order.
For `priority` roles, the first (topmost) candidate is the primary one;
subsequent candidates are fallbacks in order.

For `round_robin` roles, the saved order is only used as a tie-breaker
(e.g. when all candidates have identical last-used timestamps). Reordering
still matters for reproducibility.

### Removing a candidate

Click the **×** button on any candidate row to remove it. A role must
always have at least one candidate; the last remaining candidate cannot be
removed.

### Saving

Click **Save Role Assignments** after making changes. The server validates
all candidates before writing anything: a single invalid candidate causes
the entire save to be rejected (atomicity). Validation errors appear
inline.

## Provider failover

A dispatch attempt fails over to the next candidate when:

- The candidate's provider has **missing credentials** (API key is empty
  for a non-ACP provider).
- The candidate's model is **not in the provider's catalog**.
- The candidate is **rate-limited** (a global cooldown is active from a
  recent 429 response).
- The candidate is **budget-exceeded**: its billing model is `per_token`
  or `api`, and the configured spend limit is exhausted. Free-tier models
  (`cost_per_1k_input == 0` and `cost_per_1k_output == 0`) and
  ACP-subscription providers are **not** blocked by budget exhaustion.
- The provider returns a **startup error** (any error raised before the
  agent begins task turns, e.g. a network timeout, an auth failure, an
  SDK initialization error).

Task-level errors (errors raised after the agent begins and during normal
execution) are **not** treated as failover triggers. They go through the
existing retry-and-escalation machinery unchanged.

When all candidates are exhausted, the orchestrator marks the issue
`abnormal` with an error message listing every candidate and the reason
it was skipped.

## The provider Test button

Each provider card on the Providers page has a **Test** button that
fires a tiny probe prompt at the provider and displays the result
inline:

- **On success**: model name, response text, and latency.
- **On failure**: the normalised error reason.

The Test button:

- Does **not** create a task or issue in your backlog.
- Does **not** modify any configuration.
- Does **not** update round-robin usage state. Only real dispatches
  record usage.

Use the Test button to confirm that a newly configured provider's API
key and base URL are correct before assigning it to a role.

## Migrating from a single-candidate configuration

If your `.oompah/roles.json` was written before multi-candidate support
landed, it stores each role as a flat `provider_id` / `model` pair:

```json
[
  { "name": "fast", "provider_id": "prov-abc", "model": "gpt-4o" },
  { "name": "standard", "provider_id": "prov-abc", "model": "gpt-4" }
]
```

oompah reads this format automatically on startup and treats each entry
as a **one-candidate priority role** in memory. The file is rewritten
in the new multi-candidate format the next time you save via the
Providers page or call `PUT /api/v1/roles`.

No manual migration step is required. Your existing dispatch behaviour
is preserved: the single candidate is treated as the primary (and only)
fallback target.

## Example: priority with ACP fallback

A common pattern is to use a paid API provider as the primary and an
ACP subscription provider as a budget-safe fallback:

```
Role: standard
Strategy: priority
Candidate 1: Speedway — nvidia/llama3-70b   (api, per_token)
Candidate 2: CloudSDK — (SDK-managed)        (acp, subscription)
```

When the spend limit is reached, `Candidate 1` fails the budget preflight
and `Candidate 2` is tried. Because `CloudSDK` is subscription-billed, it
is never blocked by budget exhaustion.

## Example: round-robin across two providers

To spread load evenly across two providers, configure `round_robin` with
two candidates:

```
Role: fast
Strategy: round_robin
Candidate 1: Provider-A — nvidia/MiniMax-M2.7
Candidate 2: Provider-B — nvidia/MiniMax-M2.7
```

The orchestrator will alternate between them, always picking the one
that was used least recently. Usage state persists in
`.oompah/role_usage.json` across restarts.

## See also

- [`docs/agent-profiles.md`](./agent-profiles.md) — how agent profiles
  map to roles and set the `model_role` field.
- `plans/multi-provider-role-dispatch.md` — internal design notes on
  the selector state, dispatch ordering, and the candidate schema.
