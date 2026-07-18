---
id: OOMPAH-233
type: bug
status: In Progress
priority: 2
title: "[backend:server] Update issue API error: Cannot sync native tracker: git merge\
  \ --ff-only origin/main failed: hint: Diverging branches can't be fast-forwarded,\
  \ you need to either:\nhint:\nhint: \tgit m..."
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-18T11:58:00.682456Z'
updated_at: '2026-07-18T12:01:32.308344Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#439
  owner: lesserevil
  repo: oompah
  number: '439'
  url: https://github.com/lesserevil/oompah/issues/439
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-18T12:01:31.613433+00:00'
oompah.intake:
  missing_fields: []
  scope: small
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: pass
  last_validated_at: '2026-07-18T11:58:07.058614+00:00'
oompah.agent_run_id: 84d44fbe-089a-4fcb-a9f4-0bdd0d531c90
---
## Summary

### Problem

Oompah detected a backend error from `backend:server`:

> Update issue API error: Cannot sync native tracker: git merge --ff-only origin/main failed: hint: Diverging branches can't be fast-forwarded, you need to either:
hint:
hint: 	git merge --no-ff
hint:
hint: or:
hint:
hint: 	git rebase
hint:
hint: Disable this message with "git config set advice.diverging false"
fatal: Not possible to fast-forward, aborting.. Remediation: the local 'main' branch has diverged from origin. Run: git fetch origin && git rebase origin/main

### Desired Behavior

The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Update issue API error: Cannot sync native tracker: git merge --ff-only origin/main failed: hint: Diverging branches can't be fast-forwarded, you need to either:
hint:
hint: 	git merge --no-ff
hint:
hint: or:
hint:
hint: 	git rebase
hint:
hint: Disable this message with "git config set advice.diverging false"
fatal: Not possible to fast-forward, aborting.. Remediation: the local 'main' branch has diverged from origin. Run: git fetch origin && git rebase origin/main

### Acceptance Criteria

- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 2f7202be5cd904cd
- dedup_fingerprint: 2f7202be5cd904cd
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/439
- Requestor: @NVShawn
- Reference: lesserevil/oompah#439

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 11:58
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 11:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 11:59
---
Understanding: This issue reports that the native tracker sync fails with 'git merge --ff-only origin/main' when the local main branch has diverged from origin. My role as Duplicate Investigator is to check whether an existing task already covers this same root cause before any implementation begins. Searching now for similar tasks.
---
author: oompah
created: 2026-07-18 12:01
---
Discovery: OOMPAH-233 is NOT a duplicate.

Closest candidates reviewed:
- OOMPAH-190 (Archived): exact same error/API, but archived as 'temporary divergence manually rebased' — no code fix.
- OOMPAH-189 (Archived): same root cause, different API (Add comment), same manual resolution.
- OOMPAH-191 (Archived): same root cause, different API (Create issue), same manual resolution.
- OOMPAH-204 (Merged 2026-07-14, PR #416): **THIS IS THE CLOSEST** — same error, same API (Update issue). Added rebase fallback to _sync_from_remote() in oompah/oompah_md_tracker.py. Fix merged 2026-07-14.

Evidence OOMPAH-233 is NOT a duplicate:
1. OOMPAH-204's fix IS present in the code (lines 1010–1030 of oompah_md_tracker.py). The fix tries 'git rebase origin/<branch>' as fallback when --ff-only fails.
2. OOMPAH-233 filed on 2026-07-18 — 4 days AFTER OOMPAH-204 merged. The fix did not prevent this occurrence.
3. The error message in OOMPAH-233 is the format raised only when BOTH ff-only AND rebase fail (line 1024 in _sync_from_remote). This is a remaining gap in OOMPAH-204's fix: when there is a genuine merge conflict that rebase cannot auto-resolve.

Remaining work: OOMPAH-204 added the easy-case recovery (rebase succeeds), but the hard-case — where rebase also fails due to genuine conflicts — still raises TrackerError and triggers error_watcher. A follow-up code change is needed to either: (a) auto-reset to origin head (force sync, discarding diverged local commits), (b) emit a structured warning instead of a TrackerError so error_watcher is not triggered, or (c) add smarter retry logic. Recommended next focus: bug implementation agent to handle the rebase-also-fails case in _sync_from_remote().
---
<!-- COMMENTS:END -->
