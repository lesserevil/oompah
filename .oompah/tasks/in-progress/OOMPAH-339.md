---
id: OOMPAH-339
type: task
status: In Progress
priority: null
title: Enforce GitLab status-label authorization and audit/revert safety
parent: OOMPAH-323
children: []
blocked_by:
- OOMPAH-337
labels:
- focus-complete:duplicate_detector
- needs:feature
assignee: null
created_at: '2026-07-21T23:24:47.554460Z'
updated_at: '2026-07-22T03:58:54.579184Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: ffbd010c-d42c-4549-906c-56e6f32bd3c1
---
## Summary

Implement GitLab parity for the GitHub status-label governance model in GitLabIssueTracker and its event/polling integration as required. Canonicalize status with exactly one oompah:status:* label; identify authorized actors; record trusted status transitions; reject/mark unauthorized label changes; audit and revert to the trusted status; and exclude issues under unresolved review from dispatch candidates. Preserve fallback/backfill and terminal archive semantics consistently with GitHub. Add tests for lifecycle transitions, authorized and unauthorized actors, successful and failed reverts, candidate suppression, audit comments/records, and API errors. Acceptance: status safety and audit behavior match the GitHub-backed tracker and no unauthorized GitLab label change can dispatch work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 03:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 03:52
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 03:52
---
Understanding: Investigating OOMPAH-339 (Enforce GitLab status-label authorization and audit/revert safety) for duplicates. Will search existing tasks for similar GitLab status-label governance work before any implementation.
---
author: oompah
created: 2026-07-22 03:58
---
Focus handoff: duplicate_detector

1. **Outcome**: OOMPAH-339 is NOT a duplicate. No existing task covers GitLab status-label authorization/governance.

2. **Evidence searched**:
   - All .oompah/tasks/ states (archived, done, merged, in-progress, open, backlog) — 200+ tasks scanned
   - rg patterns: GitLab, status-label, authorized actor, trusted transition, audit, revert, governance, parity
   - plans/ and docs/ directories
   - oompah/github_tracker.py (the reference implementation) and oompah/gitlab_tracker.py (target file)

3. **Closest candidates reviewed and ruled out**:
   - OOMPAH-337 (Done): 'Build GitLabIssueTracker core REST adapter and protocol registration' — this is the foundational GitLab adapter (gitlab_tracker.py), NOT the status-label governance layer. OOMPAH-337 is correctly listed as a blocker for OOMPAH-339, and is already done. gitlab_tracker.py has no status-label authorization code yet.
   - OOMPAH-174 (Archived): mentions 'status_label_authorized_logins' only as a validation pattern reference, not an implementation task.
   - All other tasks are about state-branch features, git concurrency errors, self-hosted runners, or unrelated product features.

4. **Key evidence OOMPAH-339 is unique**:
   - oompah/github_tracker.py has an extensive status-label governance implementation (lines 1422-2741): status_label_authorized_logins, _trusted_status_ledger, _untrusted_status_issues, record_trusted_status(), _authorized_status_label_logins(), _candidate_status_label_is_trusted()
   - oompah/gitlab_tracker.py has NONE of these features — confirmed by grep returning no results
   - plans/gitlab-forge-parity.md explicitly calls out: 'enforce authorized actors, revert unauthorized status-label changes, and keep comments/audit behavior equivalent to GitHub' as separate work from the core adapter

5. **Relevant files for implementor**:
   - oompah/gitlab_tracker.py — target file, needs status-label governance added
   - oompah/github_tracker.py — reference implementation (lines 1420-2760)
   - plans/gitlab-forge-parity.md — design doc describing the expected behavior
   - tests/test_gitlab_tracker.py — existing tests (5 tests), add governance tests here

6. **Remaining work**: Full implementation as described in the task description — canonical status label enforcement, authorized actor identification, trusted transition recording, unauthorized label rejection/marking, audit/revert, candidate suppression, plus comprehensive tests.

7. **Recommended next focus**: feature
---
<!-- COMMENTS:END -->
