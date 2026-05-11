# Agent Profiles: Source of Truth

oompah lets operators define **agent profiles** — named tiers (e.g.
`quick`, `standard`, `deep`, `default`) that pin which provider, model
role, and execution mode to use for a given class of issue. Each
running agent is dispatched against exactly one profile.

Historically these profiles lived only in `WORKFLOW.md` YAML front
matter. As of oompah-zlz_2-2y7 the source of truth is the JSON file
`.oompah/agent_profiles.json`, with a one-shot migration so existing
operators don't lose their hand-tuned WORKFLOW.md profiles.

## Precedence rules

```mermaid
flowchart TD
    A[oompah boots / WORKFLOW.md reloads] --> B{OOMPAH_AGENT_PROFILES_SOURCE=workflow?}
    B -- yes --> C[Use WORKFLOW.md agent.profiles[]<br/>JSON file is ignored<br/>UI is read-only]
    B -- no --> D{".oompah/agent_profiles.json exists?"}
    D -- yes --> E[Use JSON store<br/>WARN once if YAML drifted<br/>UI is read/write]
    D -- no --> F{WORKFLOW.md has agent.profiles[]?}
    F -- yes --> G[One-shot migration:<br/>write JSON, log INFO 'Migrated N profiles…'<br/>Use the migrated list]
    F -- no --> H[Empty list]
```

In words:

1. **`OOMPAH_AGENT_PROFILES_SOURCE=workflow`** pins authority to
   `WORKFLOW.md`. The JSON file (if any) is not read; the dashboard's
   *Agent Profiles* section becomes read-only. Use this when you
   prefer to keep profile definitions checked into git alongside the
   rest of the workflow.

2. **Default** (`OOMPAH_AGENT_PROFILES_SOURCE` unset, or any value
   other than the literal string `workflow` — typos fall back to JSON
   so operators don't accidentally disable the store):

   * If `.oompah/agent_profiles.json` exists, **JSON wins**. Subsequent
     edits to `agent.profiles[]` in `WORKFLOW.md` are *ignored*. To
     nudge operators toward the right place, oompah logs a single
     WARN per process when the YAML and JSON disagree:

     ```text
     WORKFLOW.md agent.profiles[] differs from .oompah/agent_profiles.json;
     the JSON store wins. Edit profiles via the dashboard
     (or set OOMPAH_AGENT_PROFILES_SOURCE=workflow to make WORKFLOW.md
     authoritative again).
     ```

   * If `.oompah/agent_profiles.json` does NOT exist and `WORKFLOW.md`
     has `agent.profiles[]`, oompah does a **one-shot migration**:
     serialize the YAML profiles to the JSON file and log INFO

     ```text
     Migrated N profiles from WORKFLOW.md to .oompah/agent_profiles.json
     ```

     The JSON file then wins on every subsequent boot/reload.

   * If neither has profiles, the effective list is empty (default
     catch-all behavior still applies for dispatch).

## Why JSON wins by default

The dashboard exposes add / edit / delete controls for agent profiles
(`/api/v1/agent-profiles`). YAML editing requires opening
`WORKFLOW.md` and re-running the orchestrator's reload. Two write paths
fighting over the same list will eventually corrupt operator intent —
so the JSON store is the steady-state source of truth.

If you genuinely prefer YAML (e.g. your profiles are checked into git
and reviewed via PR), set:

```bash
# in .env
OOMPAH_AGENT_PROFILES_SOURCE=workflow
```

…then keep editing `WORKFLOW.md` as before. The dashboard will still
list profiles but disable the modify controls.

## File format

`.oompah/agent_profiles.json` is a JSON array. Each object has the
same keys as the YAML form, with optional fields omitted when empty:

```json
[
  {
    "name": "quick",
    "command": "claude --dangerously-skip-permissions",
    "mode": "auto",
    "provider_id": "prov-infapi-01",
    "model_role": "fast",
    "issue_types": ["chore"],
    "keywords": ["typo", "rename", "cleanup"],
    "max_priority": 4
  },
  {
    "name": "default",
    "command": "claude --dangerously-skip-permissions",
    "mode": "acp",
    "provider_id": "prov-infapi-01",
    "model_role": "fast"
  }
]
```

Writes go through the API / store (`oompah.agent_profile_store`) which
uses an atomic write-and-rename so a crash mid-edit cannot leave a
half-written file.

## Operator playbook

* **First time on a new profile JSON store:** edit `WORKFLOW.md`, boot
  oompah, then check the log for `Migrated N profiles from WORKFLOW.md
  to .oompah/agent_profiles.json`. From then on, manage profiles in
  the dashboard.
* **Reverting back to YAML authority:** set
  `OOMPAH_AGENT_PROFILES_SOURCE=workflow` in `.env`, restart. Optionally
  delete `.oompah/agent_profiles.json` to remove the redundant copy.
* **Starting fresh:** delete `.oompah/agent_profiles.json` before boot;
  if `WORKFLOW.md` has `agent.profiles[]`, the migration re-runs.
* **Validating a hand-edit of the JSON:** the file is loaded via
  `AgentProfile.from_dict`, which is tolerant of the same shapes
  `WORKFLOW.md` accepts (e.g. `keywords` as a comma-separated string).
  Invalid `mode` values fall back to `"auto"`.

## See also

* [`docs/acp-agent.md`](./acp-agent.md) — what `mode: acp` does and
  why operators set it on the catch-all `default` profile.
* [`docs/per-focus-models.md`](./per-focus-models.md) — how
  `model_role` interacts with focus-based dispatch.
* `oompah/agent_profile_store.py` — implementation; depended on by
  oompah-zlz_2-xaj (HTTP CRUD) and oompah-zlz_2-ynd (UI).
