---
id: OOMPAH-998
type: bug
status: Merged
priority: 1
title: Compose retained terminal child provenance into parent rollup authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T15:38:22.780396Z'
updated_at: '2026-08-10T17:50:40.042868Z'
work_branch: OOMPAH-998
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: oompah-940-retained-provenance-rollup-20260810
  request_fingerprint: 52409ac71c809689caef0d4569c65a8406c4f58c6fec8bda35b1a1b442827934
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-998
  head_sha: 9bf6011ac2481cbf3f73fe23085788814aa69434
  submitted_at: '2026-08-10T16:12:43.105671+00:00'
  updated_at: '2026-08-10T16:12:43.105671+00:00'
oompah.work_branch: OOMPAH-998
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-71c686a82efb
    project_id: proj-14849f1b
    task_id: OOMPAH-998
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: bb932e2008a66e421f67a69c06daa606bf5287803f641bee91690555d3c5be54
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: '[REDACTED]'
    created_at: '2026-08-10T17:50:25.550145+00:00'
    selected_ref: 9bf6011ac2481cbf3f73fe23085788814aa69434
    selected_sha: 9bf6011ac2481cbf3f73fe23085788814aa69434
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-998
    target_state: Merged
    evidence_fingerprint: bb932e2008a66e421f67a69c06daa606bf5287803f641bee91690555d3c5be54
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-10T17:50:34.440311+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-940

Triggered by OOMPAH-940. Problem: every one of OOMPAH-940s 16 children is terminal Done and its canonical child decision is terminal via trusted provenance retention, but EpicFactCollector and _epic_rollup_decision only consume target-relative LandingState.LANDED facts. A retained terminal child therefore leaves the parent permanently blocked on rollup.waiting_children with no active action or job. Existing OOMPAH-967/871, OOMPAH-981, OOMPAH-960 cover child-local terminality, live-target landing projection, and parent landing facts flowing into child decisions, but not this reverse parent composition. Scope: add an explicit authenticated parent-rollup proof/waiver for owner-retained terminal child provenance without misrepresenting it as a Git landing. Bind it to exact project, child, terminal state, target/revision, and provenance authority generation; reject missing, malformed, stale, revoked, or mismatched evidence; preserve ordinary target-relative landing requirements for non-retained children. Relevant code: oompah/epic_workflow.py, workflow fact/provenance composition, rollup decision and durable reconciliation. Add unit/integration/restart regressions for historical children 956, 960-962, 967-968, 979-980; prove a retained exact child can satisfy the parent obligation, stale/revoked retention cannot, no repeated landing job is generated, and a stable restart produces the same total decision. Acceptance: OOMPAH-940-like parents roll up naturally from exact trusted evidence, non-retained children remain fail-closed, current divergence/exhaustion stays zero, and focused plus complete protected gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 16:12
---
Implementation complete at 9bf6011ac2481cbf3f73fe23085788814aa69434 and pushed to origin/OOMPAH-998. Exact retained terminal child provenance now composes as a scoped parent-rollup waiver without forging Git landing or cleanup authority; generation-zero, revocation races, scope/head/route mismatches, restart idempotency, and cleanup non-authority are covered. Verification: 217 focused tests passed locally; independent implementation/review suites passed 358 and 121 tests; changed-code lint, diff check, terminal-audit scan, and secret scan pass.
---
author: oompah
created: 2026-08-10 16:12
---
Compose exact retained-child provenance into parent rollup authority; fail closed on stale/revoked/mismatched evidence and prevent waiver reuse as landing or cleanup authority.
---
author: oompah
created: 2026-08-10 17:50
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: [REDACTED]
---
author: oompah
created: 2026-08-10 17:50
---
Merged exact OOMPAH-998 recovery commit through protected PR #799 and deployed it at 0ce6c3131af200ab89090c13255c3606fc8d753b; live generation 1529 is healthy with zero current divergence/exhaustion.
---
<!-- COMMENTS:END -->
