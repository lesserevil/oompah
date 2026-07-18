---
id: OOMPAH-233
type: bug
status: Done
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
updated_at: '2026-07-18T12:08:57.729241Z'
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
oompah.agent_run_id: 47703e36-daf3-4d6d-aa37-ae89faebe7d3
oompah.task_costs:
  total_input_tokens: 91247
  total_output_tokens: 8582
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 91247
      output_tokens: 8582
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 15
    output_tokens: 7693
    cost_usd: 0.0
    recorded_at: '2026-07-18T12:01:56.967687+00:00'
  - profile: default
    model: unknown
    input_tokens: 91232
    output_tokens: 889
    cost_usd: 0.0
    recorded_at: '2026-07-18T12:02:49.742319+00:00'
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
author: oompah
created: 2026-07-18 12:01
---
Focus handoff: duplicate_detector

1. Outcome: OOMPAH-233 is NOT a duplicate. The closest prior task is OOMPAH-204 (Merged), which added a rebase fallback to _sync_from_remote() in oompah/oompah_md_tracker.py. That fix is present in the codebase but does not cover the case where rebase also fails.

2. Relevant files and evidence:
   - oompah/oompah_md_tracker.py lines 983–1030: _sync_from_remote() with the OOMPAH-204 rebase fallback in place
   - tests/test_oompah_md_tracker.py: tests added by OOMPAH-204 (test_ff_only_failure_rebase_recovery_succeeds, test_commit_and_push_retry_rebase_recovery_on_diverged_branch)
   - OOMPAH-204 (Merged 2026-07-14 via PR #416): the prior fix; its fix handles --ff-only fails + rebase succeeds, but not --ff-only fails + rebase also fails
   - OOMPAH-233 error fingerprint: 2f7202be5cd904cd (different from OOMPAH-204's f289e9452f5913f0, confirming it is a separate incident/code path)
   - The TrackerError at line 1024 in _sync_from_remote() is what fires when both paths fail

3. Remaining work: Implement handling for the 'both ff-only and rebase fail' case in _sync_from_remote(). Options: (a) auto-reset local to origin/branch (force-sync, discarding any un-pushed local task commits — acceptable since the remote version wins), (b) catch the TrackerError at the API layer and demote it from an error to a logged warning so error_watcher is not triggered for this known transient case. Option (a) is cleaner since it recovers and continues; option (b) suppresses noise but leaves the diverged state unresolved. Risk: any fix must not regress the OOMPAH-10 guard (avoid 'git pull --rebase').

4. Recommended next focus: bug/feature implementation agent to fix _sync_from_remote() for the rebase-also-fails case and add a regression test.
---
author: oompah
created: 2026-07-18 12:01
---
Agent completed successfully in 178s (7708 tokens)
---
author: oompah
created: 2026-07-18 12:02
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 33, Tool calls: 18
- Tokens: 15 in / 7.7K out [7.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 58s
- Log: OOMPAH-233__20260718T115903Z.jsonl
---
author: oompah
created: 2026-07-18 12:02
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-18 12:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 12:02
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-18 12:02
---
Agent completed successfully in 30s (92121 tokens)
---
author: oompah
created: 2026-07-18 12:02
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 91.2K in / 889 out [92.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 30s
- Log: OOMPAH-233__20260718T120224Z.jsonl
---
author: oompah
created: 2026-07-18 12:02
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-233`. Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-18 12:03
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-18 12:03
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-18 12:03
---
Understanding: Picking up from duplicate_detector handoff. Root cause: _sync_from_remote() in oompah/oompah_md_tracker.py has a two-step recovery (ff-only → rebase), but when both fail it raises TrackerError which triggers error_watcher. Fix: add a third recovery step — 'git reset --hard origin/<branch>' — to force-sync local to remote when rebase also fails, since remote wins for tracker state. Will implement + add regression test.
---
author: oompah
created: 2026-07-18 12:08
---
Implementation: Added a third recovery step to _sync_from_remote() in oompah/oompah_md_tracker.py.

Previous behavior: when both ff-only and rebase failed, a TrackerError was raised immediately, triggering error_watcher.

New behavior: after rebase --abort, attempt 'git reset --hard origin/<branch>' to force-sync local to remote. Since remote is authoritative for tracker task files, discarding un-pushable local commits is safe and unblocks the write. Only when all three recovery paths (ff-only, rebase, reset --hard) fail is a TrackerError raised.

Test changes:
- Updated test_ff_only_failure_raises_tracker_error_with_remediation: mock reset --hard as failing too, so the TrackerError assertion still holds for the all-three-fail case.
- Added test_ff_only_failure_rebase_fails_reset_recovers: new regression test for OOMPAH-233, verifying silent recovery via reset when both ff-only and rebase fail.
---
author: oompah
created: 2026-07-18 12:08
---
Verification: All 9055 tests pass (make test). The 6 git-sync tests all pass including the new test_ff_only_failure_rebase_fails_reset_recovers regression test.
---
author: oompah
created: 2026-07-18 12:08
---
Completion: Added a third sync recovery path in _sync_from_remote() — git reset --hard origin/<branch> — that fires when both ff-only and rebase fail. This is the case that triggered OOMPAH-233: the error_watcher was catching TrackerError raised by the all-fail path. Now the reset --hard silently recovers (with a warning log), and error_watcher is only triggered for genuinely unrecoverable states where even the hard reset fails. One new regression test (test_ff_only_failure_rebase_fails_reset_recovers) added; existing TrackerError test updated to also fail the reset so its assertion remains valid.
---
author: oompah
created: 2026-07-18 12:08
---
Added git reset --hard origin/<branch> as third fallback in _sync_from_remote() when both ff-only and rebase fail; added regression test. error_watcher no longer triggered for the normal diverged-branch recovery case.
---
author: oompah
created: 2026-07-18 12:08
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 16
- Tokens: 35 in / 544 out [579 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 38s
- Log: OOMPAH-233__20260718T120323Z.jsonl
---
<!-- COMMENTS:END -->
