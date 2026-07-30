---
id: OOMPAH-630
type: task
status: Open
priority: null
title: Fetch rollup targets before judging child landing evidence
parent: OOMPAH-584
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T23:37:58.090708Z'
updated_at: '2026-07-30T23:48:48.797887Z'
work_branch: epic-OOMPAH-584--task-OOMPAH-630
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ece5ae838a442263961233e744d0713b8bdfd1d7dea7b9ab6694bcdf5513ca2c
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: cd943ffa-791b-4c75-a4f7-1c3399506c3c
  claim_owner: 9bd6f53b-ba8c-40b8-855a-73f609dcfa82
  claimed_at: '2026-07-30T23:48:42.026677+00:00'
  claim_expires_at: '2026-07-31T00:18:42.026677+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 9b79b103-3d7a-4969-8c61-03f2a0555795
oompah.work_branch: epic-OOMPAH-584--task-OOMPAH-630
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-584--task-OOMPAH-630
  base_branch: epic-OOMPAH-584
  base_sha: c45e47bb3bdf8f3424357dd499010d52322bd7cc
  updated_at: '2026-07-30T23:48:46.655989+00:00'
---
## Summary

Implementation scope: eliminate the post-merge race where reconcile_merged_epic_children compares child branches against a stale local remote-tracking ref and demotes genuinely landed Done children to Needs Human. Before _child_landing_evidence_block_reason evaluates ancestry or patch equivalence, refresh the exact authoritative rollup target ref with a bounded non-interactive fetch, or otherwise use the merge event's authoritative target SHA. Fail closed on an actual fetch/containment error without mutating a Done child based solely on stale cached refs. Preserve redacted diagnostics and the existing runtime budget. Relevant code: oompah/orchestrator.py rollup landing-evidence helpers and merged-label reconciliation. Tests: reproduce a stale origin/<parent-epic> ref that does not contain the child while the remote target does; prove refresh recognizes direct ancestry and patch equivalence; cover fetch failure/timeouts, nested epics, and genuinely unlanded work. Acceptance criteria: a child head that is an ancestor of the just-merged target cannot be demoted; genuinely unlanded children still become Needs Human; focused epic-strategy tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 23:38
---
Claimed directly by the operator Codex session because the live scheduler is blocked in a stale cleanup sweep. Reproducer confirmed: each affected child head is an ancestor of origin/epic-OOMPAH-584, but reconciliation used a stale target ref and demoted it.
---
author: oompah
created: 2026-07-30 23:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 23:48
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
