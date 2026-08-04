---
id: OOMPAH-746
type: bug
status: Open
priority: 1
title: Resolve terminal-audit evidence from canonical epic branches when work_branch
  is absent
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T00:40:18.391859Z'
updated_at: '2026-08-04T00:41:19.096222Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1435d8d231ea47878cdbfb3e8bec02bd7c390370d729fd2852567f034a214a0e
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 89603f86-e1cd-4772-80ca-c6102a700df1
  claim_owner: b6e50576-eec3-4dce-bc89-fe685f70768e
  claimed_at: '2026-08-04T00:41:06.963763+00:00'
  claim_expires_at: '2026-08-04T01:11:06.963763+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 1601c4e6-8ecb-458a-9023-72c1f2e96e48
---
## Summary

Triggered by: EXOCOMP-130

Live reproduction: EXOCOMP-130 exhausted all terminal-audit attempts before auditor launch because its task detail has no work_branch and evidence resolution tried only origin/EXOCOMP-130. The canonical branch origin/epic-EXOCOMP-130 exists at 7bf5506c, so valid immutable evidence is available but the resolver derives the wrong ref. Implementation scope: make terminal-audit staging resolve shared and nested epic branch names from authoritative issue type, parent, project, and persisted transition metadata; persist the exact work branch and immutable SHA when requesting a terminal transition; verify the remote ref and fail closed on ambiguity; distinguish absent metadata, deleted branches, and provider failures; and make corrected rearm/restart idempotent without reopening implementation. Preserve the immutable-SHA recovery delivered by OOMPAH-671. Relevant code includes terminal-audit staging and evidence collection in oompah/orchestrator.py plus project branch-resolution and transition metadata helpers. Required tests: reproduce EXOCOMP-130 where origin/ID is absent but origin/epic-ID exists; cover nested epics, exact SHA snapshotting, deleted branches with retained immutable evidence, ambiguous refs, restart/rearm, and cross-project naming. Acceptance criteria: a terminal request for an epic with absent work_branch resolves and audits the canonical epic ref exactly once; unsafe ambiguity remains blocked with an actionable diagnosis; existing deleted-branch recovery stays green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 00:41
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 00:41
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
