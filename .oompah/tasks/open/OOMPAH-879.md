---
id: OOMPAH-879
type: task
status: Open
priority: null
title: Prevent concurrent duplicate epic-rebase tasks for one epic generation
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T10:40:35.699435Z'
updated_at: '2026-08-07T10:47:06.974761Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-879
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4b9ec0bb21e4c1d3a984ccccb80a5a09a30fe3b98a5295807976e833d679c42d
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: b4fc6ed2-17dd-46b8-8e3e-903b3d371548
  claim_owner: 0c3fdd32-3af4-41c2-89eb-bba40d25c9aa
  claimed_at: '2026-08-07T10:44:00.967265+00:00'
  claim_expires_at: '2026-08-07T11:14:00.967265+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8601033e-1631-489a-a84b-303631ab28c6
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-879
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-879
  base_branch: epic-OOMPAH-763
  base_sha: 04fa6781091efc6f11b952b9f1b35123facce64f
  updated_at: '2026-08-07T10:44:34.962991+00:00'
---
## Summary

Live reproduction 2026-08-07: OOMPAH-877 already represented the required epic-OOMPAH-763 rebase and was under an active direct-owner claim while waiting for Ready child heads OOMPAH-854@91e76723e and OOMPAH-866@f959c1827 to integrate. The stale-epic scheduler nevertheless auto-filed and dispatched duplicate OOMPAH-878 against the same epic generation and clean shared epic worktree at 04fa678, which would have published an obsolete rebase before those children landed. Implementation scope: make rebase filing/dispatch an atomic per-project+epic+target-generation decision; treat every nonterminal rebase task, active owner claim, running generation, and durable rebase job as mutually exclusive authority; re-evaluate prerequisites and epic head immediately before worker admission and before push; archive/supersede duplicate auto-filed tasks without provider work. Relevant code: epic staleness/rebase filing, duplicate preflight qualification, direct-owner admission, durable workflow jobs, and shared epic worktree fencing. Required tests: a claimed existing rebase prevents a second filing and dispatch; concurrent staleness ticks yield one task; a newly integrated child invalidates an older rebase generation before push; restart preserves exclusivity; a genuinely new main/epic generation can file exactly one successor after prior terminal completion. Acceptance: at most one actionable rebase authority exists per epic generation, and no stale duplicate can mutate or publish the epic branch.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 10:44
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 10:44
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 10:47
---
Live stale-generation reproduction during OOMPAH-877 sequencing (2026-08-07): the first prematurely dispatched direct epic-rebase helper captured integration.base_sha=04fa6781091efc6f11b952b9f1b35123facce64f. OOMPAH-854, OOMPAH-866, and possibly OOMPAH-846 will integrate into epic-OOMPAH-763 before the operator-owned rebase starts. The task CLI submit path sends no base_sha and _submission_record prefers the existing value, so an otherwise correct later submission would retain 04fa678 and omit newly integrated child ranges from the direct-rebase generation. The operator will work around this in flight by using the authenticated standard submit endpoint with explicit base_sha equal to the exact pre-rebase origin/epic-OOMPAH-763 head and CLI-equivalent clean/remote/branch/head evidence. Acceptance should cover refreshing/superseding an older helper generation after new child integration, while preserving the older value as forensic evidence until authoritative publication.
---
<!-- COMMENTS:END -->
