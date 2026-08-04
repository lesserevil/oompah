---
id: OOMPAH-807
type: task
status: Open
priority: null
title: Allow revisionless audits for metadata-only Archived dispositions
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T21:29:59.448729Z'
updated_at: '2026-08-04T21:37:20.193643Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-807
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5d8823017faedc20e0c4fc8b58a6f30dc19338faf49501d69680a12207539d23
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 0f4c566b-60ad-495b-994d-086ae90260fd
  claim_owner: f75f2e47-c230-48b7-9af8-09eea50f8e9b
  claimed_at: '2026-08-04T21:36:39.967987+00:00'
  claim_expires_at: '2026-08-04T22:06:39.967987+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: e576c151-0a32-4fd2-86a3-e96876ea07de
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-807
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-807
  base_branch: epic-OOMPAH-763
  base_sha: f1e7925b7263f980517f943291102c8c83335ed2
  updated_at: '2026-08-04T21:37:12.679978+00:00'
---
## Summary

Bug reproduction: OOMPAH-803 is a Backlog metadata duplicate of OOMPAH-775 with a structured replacement source and no implementation branch. Requesting Archived correctly enters In Validation, but every terminal-audit attempt fails before launch with 'terminal audit evidence has no safely resolvable revision' after trying origin/OOMPAH-803. Implementation scope: separate code-bearing completion audits from metadata-only Archived dispositions; for duplicate/obsolete retirement, validate structured reason, source/replacement reference, no active owner/worker/retry/review, no unresolved children/dependencies, and unchanged task requirements without requiring or inventing a code revision/worktree. Preserve fail-closed immutable-revision rules for Done/Merged and code-bearing Archived paths. Relevant code: oompah/orchestrator.py _create_workspace_for_auditor, ArchivedEvidenceCollector/terminal coordinator and enforcement, audit launch/recovery projections. Required tests: revisionless Backlog duplicate with valid replacement archives; missing replacement/reason fails actionable; active work/review blocks; code-bearing immutable SHA remains fail-closed; restart/retry does not loop transport/launch failures; OOMPAH-803 regression. Acceptance: metadata-only Archived audits launch/finalize without a fake branch, unsafe retirement remains blocked, and audit health does not report revision resolution as a transport failure.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 21:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 21:37
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
