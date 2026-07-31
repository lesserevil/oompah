---
id: OOMPAH-653
type: bug
status: Open
priority: 1
title: Make terminal-audit success and owner override retire every duplicate record
  and alert
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T09:02:42.727629Z'
updated_at: '2026-07-31T09:03:36.673128Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Two live regressions remained after OOMPAH-643 merged. First, OOMPAH-648 audit attempt audit-db48e6cb6d3e recorded Audit PASS with safe evidence at 08:37, but another audit for the same terminal transition was dispatched at 08:38, retried, exhausted candidates, and moved the already-passed task to Needs Human. Second, OOMPAH-644 received an authorized owner override to Merged (override-b9bd25c5c20a), yet terminal_audit:no_independent_candidate for the superseded audit remained an error through multiple ticks and a full service restart. Implementation scope: enforce one canonical live audit identity per project/task/target-state/evidence fingerprint; make pass/override atomic and idempotent; cancel/supersede all sibling pending or in-progress records; prevent reconciliation from recreating an audit for the same applied fingerprint; remove their actionable alert identities and stale pending timestamps from health/state while retaining historical counters. Close races among auditor result persistence, task status movement, reconcile scans, owner override, and restart recovery. Relevant files: terminal_transition_coordinator.py, orchestrator audit scan/dispatch/result paths, terminal audit persistence/observability/health, state alert aggregation, and native task status reconciliation. Required deterministic tests: barrier between PASS persistence and reconcile scan; duplicate records already queued/running when PASS lands; override concurrent with no-candidate routing; restart after pass/override; repeated callbacks; task changes fingerprint after completion creates exactly one new audit; project isolation. Acceptance: OOMPAH-648-style PASS cannot be followed by a second audit or Needs Human, OOMPAH-644-style override immediately clears all superseded actionable alerts and stays clear across restart, historical evidence remains queryable, focused audit race tests, terminal mutation scan, and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 09:03
---
Post-override state proof: terminal_audit health reports pending=0, in_progress=0, failure_count=0, degraded=false, yet state alerts still emits terminal_audit:no_independent_candidate for both superseded OOMPAH-644 and OOMPAH-648 audits across ticks/restart. Alert invalidation is therefore diverging from the canonical health/audit record lifecycle.
---
<!-- COMMENTS:END -->
