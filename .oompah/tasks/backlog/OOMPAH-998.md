---
id: OOMPAH-998
type: bug
status: Backlog
priority: 1
title: Compose retained terminal child provenance into parent rollup authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T15:38:22.780396Z'
updated_at: '2026-08-10T15:38:22.780396Z'
work_branch: null
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
---
## Summary

Triggered by: OOMPAH-940

Triggered by OOMPAH-940. Problem: every one of OOMPAH-940s 16 children is terminal Done and its canonical child decision is terminal via trusted provenance retention, but EpicFactCollector and _epic_rollup_decision only consume target-relative LandingState.LANDED facts. A retained terminal child therefore leaves the parent permanently blocked on rollup.waiting_children with no active action or job. Existing OOMPAH-967/871, OOMPAH-981, OOMPAH-960 cover child-local terminality, live-target landing projection, and parent landing facts flowing into child decisions, but not this reverse parent composition. Scope: add an explicit authenticated parent-rollup proof/waiver for owner-retained terminal child provenance without misrepresenting it as a Git landing. Bind it to exact project, child, terminal state, target/revision, and provenance authority generation; reject missing, malformed, stale, revoked, or mismatched evidence; preserve ordinary target-relative landing requirements for non-retained children. Relevant code: oompah/epic_workflow.py, workflow fact/provenance composition, rollup decision and durable reconciliation. Add unit/integration/restart regressions for historical children 956, 960-962, 967-968, 979-980; prove a retained exact child can satisfy the parent obligation, stale/revoked retention cannot, no repeated landing job is generated, and a stable restart produces the same total decision. Acceptance: OOMPAH-940-like parents roll up naturally from exact trusted evidence, non-retained children remain fail-closed, current divergence/exhaustion stays zero, and focused plus complete protected gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

