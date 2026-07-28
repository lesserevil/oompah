---
id: OOMPAH-516
type: chore
status: Backlog
priority: 1
title: Deploy OOMPAH-505 and apply live Claude/Codex tier roles
parent: null
children: []
blocked_by: []
labels:
- needs:human
assignee: null
created_at: '2026-07-28T15:52:20.003932Z'
updated_at: '2026-07-28T15:52:20.003932Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-505

Operator-access follow-up from OOMPAH-505. Scope: deploy commit 020199d32 (or its merged equivalent) to the managed Oompah runtime, using the actual service checkout and the normal draining restart with health/readiness verification; do not start a shadow instance from an agent worktree. Before configuration, capture a recoverable snapshot of .oompah/roles.json and the deployed revision. Resolve the existing ACP providers by backend/name at runtime (do not hardcode local provider IDs in production defaults), then atomically configure round-robin candidates: fast = Claude/fable + Codex/gpt-5.6-luna; standard = Claude/sonnet + Codex/gpt-5.6-terra; deep = Claude/opus + Codex/gpt-5.6-sol. Preserve the default role, providers.json credentials/settings, provider health, project whitelist, and usage state. Verification: service reports a new healthy instance; role configuration round-trips with all six exact mappings; Claude and Codex health/startup checks pass; representative running tasks report the selected provider/model in state and telemetry. Roll back the role snapshot and deployed revision if health/readiness or model startup validation fails. Acceptance: updated UI is live, six mappings are live, telemetry is confirmed, and rollback evidence is recorded on this task.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

