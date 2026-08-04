---
id: OOMPAH-807
type: task
status: Backlog
priority: null
title: Allow revisionless audits for metadata-only Archived dispositions
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T21:29:59.448729Z'
updated_at: '2026-08-04T21:29:59.448729Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Bug reproduction: OOMPAH-803 is a Backlog metadata duplicate of OOMPAH-775 with a structured replacement source and no implementation branch. Requesting Archived correctly enters In Validation, but every terminal-audit attempt fails before launch with 'terminal audit evidence has no safely resolvable revision' after trying origin/OOMPAH-803. Implementation scope: separate code-bearing completion audits from metadata-only Archived dispositions; for duplicate/obsolete retirement, validate structured reason, source/replacement reference, no active owner/worker/retry/review, no unresolved children/dependencies, and unchanged task requirements without requiring or inventing a code revision/worktree. Preserve fail-closed immutable-revision rules for Done/Merged and code-bearing Archived paths. Relevant code: oompah/orchestrator.py _create_workspace_for_auditor, ArchivedEvidenceCollector/terminal coordinator and enforcement, audit launch/recovery projections. Required tests: revisionless Backlog duplicate with valid replacement archives; missing replacement/reason fails actionable; active work/review blocks; code-bearing immutable SHA remains fail-closed; restart/retry does not loop transport/launch failures; OOMPAH-803 regression. Acceptance: metadata-only Archived audits launch/finalize without a fake branch, unsafe retirement remains blocked, and audit health does not report revision resolution as a transport failure.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

