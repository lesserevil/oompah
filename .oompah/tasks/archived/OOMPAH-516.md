---
id: OOMPAH-516
type: chore
status: Archived
priority: 1
title: Deploy OOMPAH-505 and apply live Claude/Codex tier roles
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:52:20.003932Z'
updated_at: '2026-08-02T18:21:05.905055Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-e2dbbc6c434d
    project_id: proj-14849f1b
    task_id: OOMPAH-516
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a4ce14582582a9a58f03f6d6b4d8ae0fd9ef7479629731815c0619b6bfb00f81
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Authorized owner cleanup: completed operator deployment has durable live-verification
      comments and no merge artifact; terminal Archived is the truthful lifecycle
      state. OOMPAH-699 tracks automatic convergence.'
    created_at: '2026-08-02T18:20:58.865035+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-516
    target_state: Archived
    evidence_fingerprint: a4ce14582582a9a58f03f6d6b4d8ae0fd9ef7479629731815c0619b6bfb00f81
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-02T18:21:04.904014+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-505

Operator-access follow-up from OOMPAH-505. Scope: deploy commit 020199d32 (or its merged equivalent) to the managed Oompah runtime, using the actual service checkout and the normal draining restart with health/readiness verification; do not start a shadow instance from an agent worktree. Before configuration, capture a recoverable snapshot of .oompah/roles.json and the deployed revision. Resolve the existing ACP providers by backend/name at runtime (do not hardcode local provider IDs in production defaults), then atomically configure round-robin candidates: fast = Claude/fable + Codex/gpt-5.6-luna; standard = Claude/sonnet + Codex/gpt-5.6-terra; deep = Claude/opus + Codex/gpt-5.6-sol. Preserve the default role, providers.json credentials/settings, provider health, project whitelist, and usage state. Verification: service reports a new healthy instance; role configuration round-trips with all six exact mappings; Claude and Codex health/startup checks pass; representative running tasks report the selected provider/model in state and telemetry. Roll back the role snapshot and deployed revision if health/readiness or model startup validation fails. Acceptance: updated UI is live, six mappings are live, telemetry is confirmed, and rollback evidence is recorded on this task.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:52
---
Moved to Needs Human from the dashboard/API. Human action required: inspect OOMPAH-516 (Deploy OOMPAH-505 and apply live Claude/Codex tier roles), add the specific decision, missing information, or manual fix needed, then move the task back to Open when it is ready for agents again.
---
author: oompah
created: 2026-07-28 15:52
---
Requires operator write/restart access to the managed runtime; the agent sandbox exposes only read-only runtime metadata and prohibits loopback self-calls.
---
author: oompah
created: 2026-07-28 17:28
---
Resolved: the operator rollout has already been completed. The running service exposes manual model selection for Claude and Codex, and GET /api/v1/roles resolves the live round-robin mappings as fast/default = Claude haiku + Codex gpt-5.6-luna, standard = Claude sonnet + Codex gpt-5.6-terra, and deep = Claude opus + Codex gpt-5.6-sol. The task's original Claude fable value is superseded: two live dispatches rejected literal fable before tool use, while the direct haiku smoke test resolved successfully. Provider IDs were resolved from the live store rather than hardcoded, and OOMPAH-505 records the deployment and verification evidence. No human decision or manual action remains.
---
author: oompah
created: 2026-07-28 17:28
---
Deployment complete: live Claude/Codex round-robin tiers resolve successfully; corrected the unavailable Claude fast mapping from fable to haiku.
---
author: oompah
created: 2026-08-02 18:20
---
Owner reconciliation: this operator-only deployment task completed on 2026-07-28, as recorded in comments #3-4; the live role configuration was verified and no code branch or merge remains. Archiving the completed operational record. Root-cause tracking for stranded historical Done states: OOMPAH-699.
---
author: oompah
created: 2026-08-02 18:21
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Authorized owner cleanup: completed operator deployment has durable live-verification comments and no merge artifact; terminal Archived is the truthful lifecycle state. OOMPAH-699 tracks automatic convergence.
---
<!-- COMMENTS:END -->
