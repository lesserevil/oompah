---
id: OOMPAH-779
type: task
status: Ready to Integrate
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
updated_at: '2026-08-04T16:09:36.110789Z'
work_branch: null
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
<!-- COMMENTS:END -->
