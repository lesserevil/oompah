---
id: OOMPAH-730
type: bug
status: Open
priority: 1
title: Execute and reconcile safe container-cycle repairs automatically
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T16:59:59.720852Z'
updated_at: '2026-08-03T17:01:51.127508Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 928280678fe228e47b31ccf951c660383dfc236e89deea557dab536986904912
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 9bba1c04-085e-4351-8ab5-c267a90db9c8
  claim_owner: 8a58fb27-42d0-40cf-8dc2-70615b9783dc
  claimed_at: '2026-08-03T17:01:38.264217+00:00'
  claim_expires_at: '2026-08-03T17:31:38.264217+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: e480a9d2-7698-4c65-a85c-8d4909d8e07e
---
## Summary

Triggered by: OOMPAH-718

Production follow-up after deploying OOMPAH-718 on 2026-08-03. The detector correctly found the live Exocomp container cycle EXOCOMP-130 -> EXOCOMP-134 -> EXOCOMP-131 -> EXOCOMP-130 and selected an exact safe repair: deliver EXOCOMP-171=f1e60cb4a3aa94d1af2cdbdf4767e6a2ed4cc1fa and EXOCOMP-172=3377d707470a4dbe27fd9c962c0acb4e95e1289d through common authoritative parent EXOCOMP-127. However, it only cancelled 20 Ready queue rows and emitted an alert; it provides no supported operation to apply the already-selected repair or automatically requeue the fenced rows afterward. The queue is therefore intentionally diagnosed but still requires manual Git surgery and tracker reconciliation.

Implementation scope:
- Add a project-owner-authorized or policy-authorized executor for a container-cycle repair selected by the OOMPAH-718 analyzer.
- Under compare-and-swap leases, advance the common authoritative container only when the selected prerequisite SHA is a descendant containing no commits outside the declared prerequisite closure.
- Synchronize that exact authoritative ancestry into only the affected dependent containers using the existing parent-only repair policy; never import arbitrary sibling heads.
- Detect merge conflicts before changing remote refs and route only conflicted containers to an actionable repair task while independent containers continue.
- After reachability is proven, atomically restore cancelled Ready queue rows whose private heads still match, clear cycle diagnostics/alerts, and resume normal ordered integration.
- Make restart/idempotency safe: a partially applied parent push or child synchronization must converge without duplicate merge commits, lost private heads, or permanent cancelled rows.
- Expose repair phase, exact SHAs, ref compare-and-swap evidence, affected rows, and any conflict in API/dashboard diagnostics.

Required tests:
- Reproduce the live EXOCOMP-130/134/131 cycle with exact 171/172 ancestry; apply the repair and prove all 20 fenced rows return to ordinary queue evaluation.
- Prove a prerequisite-descendant fast-forward through the common parent and parent-only child synchronization preserve exact SHA ancestry.
- Reject a selected SHA containing an unrelated sibling commit.
- Cover diverged child branch clean merge, child conflict, remote-ref race, changed private queue head, restart after each durable step, and repeated execution.
- Prove alerts clear only after branch reachability and queue restoration are both durable.
- Run focused container graph/integration queue/project Git tests and make test.

Acceptance criteria:
- A safely repairable detected container cycle no longer stops at an operator-only alert.
- The exact selected prerequisite closure reaches the affected branches and matching cancelled rows resume automatically.
- Unsafe or conflicting cases fail closed with precise scoped tasks and no unrelated code propagation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 17:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 17:01
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
