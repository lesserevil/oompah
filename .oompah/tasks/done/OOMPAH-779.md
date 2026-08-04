---
id: OOMPAH-779
type: task
status: Done
priority: 1
title: Run WorkDecision in shadow mode and expose divergence diagnostics
parent: OOMPAH-765
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-777
labels: []
assignee: null
created_at: '2026-08-04T13:58:55.460558Z'
updated_at: '2026-08-04T16:23:33.983049Z'
work_branch: epic-OOMPAH-765
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-779
  head_sha: 40e46bf8e41c15a0a89529694cbb3aa3580f2f19
  submitted_at: '2026-08-04T16:09:26.258699+00:00'
  updated_at: '2026-08-04T16:09:26.258699+00:00'
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-1af133e37d3f
    project_id: proj-14849f1b
    task_id: OOMPAH-779
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4083f79d9641a27e75062d175962b284ef7958a9d825dc92b26a2a3d81e3f9bd
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project owner directly verified commit 40e46bf8e: 362 relevant tests,
      terminal mutation scan, secret scan, and exact git ancestry passed; the exact
      head is now the tip of epic-OOMPAH-765.'
    created_at: '2026-08-04T16:10:15.923579+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-779
    target_state: Done
    evidence_fingerprint: 4083f79d9641a27e75062d175962b284ef7958a9d825dc92b26a2a3d81e3f9bd
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-04T16:10:30.590956+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
oompah.work_branch: epic-OOMPAH-765
---
## Summary

Integrate fact collection/evaluation as a no-mutation shadow path controlled by .env/.env.example OOMPAH_* modes. Compare WorkDecision with legacy dispatch, integration, audit, review, watchdog, and UI classifications; record structured divergences with task/evidence versions and expected owner, without global warning spam. Add a project/task diagnostic API returning current facts, decision, and legacy comparison with secret-safe evidence. Required tests: feature mode reload, zero side effects in shadow, divergence dedup/clearing, API auth/redaction, stale snapshot generations, and WebSocket/state visibility. Acceptance: production can soak shadow evaluation and every divergence is actionable and reproducible before enforcement.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 16:09
---
Implemented commit 40e46bf8e on canonical branch OOMPAH-779. Added bounded no-mutation WorkDecision shadow sweeps, structured deduplicated/clearing divergence diagnostics, stale-generation fencing, secret redaction and defensive copies, authenticated per-task API, state/WebSocket aggregate visibility, environment-only rollout controls, graceful-drain handling, and design documentation. Verification: 25 focused tests passed; 337 adjacent workflow/facts/config/auth/WebSocket/shutdown tests passed; terminal mutation scan passed; secret scan and git diff checks passed.
---
author: oompah
created: 2026-08-04 16:09
---
Implemented no-mutation workflow decision shadow mode with actionable redacted diagnostics and production-soak visibility; 362 relevant tests pass.
---
author: oompah
created: 2026-08-04 16:10
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Project owner directly verified commit 40e46bf8e: 362 relevant tests, terminal mutation scan, secret scan, and exact git ancestry passed; the exact head is now the tip of epic-OOMPAH-765.
---
<!-- COMMENTS:END -->
