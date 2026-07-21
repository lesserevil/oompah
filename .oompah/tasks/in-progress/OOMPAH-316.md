---
id: OOMPAH-316
type: bug
status: In Progress
priority: 2
title: '[backend:server] Fetch issues failed for project exocomp: State branch ''oompah/state/proj-c260b117''
  does not exist locally or at origin/''oompah/state/proj-c260b117''. Run the bootstrap
  or migration ...'
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
- focus-complete:general
assignee: null
created_at: '2026-07-21T18:20:20.146747Z'
updated_at: '2026-07-21T19:12:15.886395Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#471
  owner: lesserevil
  repo: oompah
  number: '471'
  url: https://github.com/lesserevil/oompah/issues/471
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-21T19:02:02.408258+00:00'
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
  last_validated_at: '2026-07-21T18:20:35.323844+00:00'
oompah.agent_run_id: fc223746-7f9f-408f-9d44-31e78cc8b8bb
oompah.task_costs:
  total_input_tokens: 1139971
  total_output_tokens: 11082
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1139971
      output_tokens: 11082
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 175055
    output_tokens: 1362
    cost_usd: 0.0
    recorded_at: '2026-07-21T18:50:53.962647+00:00'
  - profile: deep
    model: unknown
    input_tokens: 443995
    output_tokens: 2285
    cost_usd: 0.0
    recorded_at: '2026-07-21T18:52:40.845233+00:00'
  - profile: deep
    model: unknown
    input_tokens: 19
    output_tokens: 4214
    cost_usd: 0.0
    recorded_at: '2026-07-21T18:55:16.758663+00:00'
  - profile: deep
    model: unknown
    input_tokens: 520902
    output_tokens: 3221
    cost_usd: 0.0
    recorded_at: '2026-07-21T19:11:48.035088+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:server`:

> Fetch issues failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

### Desired Behavior

The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Fetch issues failed for project exocomp: State branch 'oompah/state/proj-c260b117' does not exist locally or at origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow to create it before enabling state_branch_enabled=True for this project. Normal tracker reads must not create remote branches.

### Acceptance Criteria

- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 9a803f3b8b56abc0
- dedup_fingerprint: 9a803f3b8b56abc0
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/471
- Requestor: @lesserevil
- Reference: lesserevil/oompah#471

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 18:50
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 18:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 18:50
---
Agent completed successfully in 50s (176417 tokens)
---
author: oompah
created: 2026-07-21 18:50
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 3
- Tokens: 175.1K in / 1.4K out [176.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 50s
- Log: OOMPAH-316__20260721T185006Z.jsonl
---
author: oompah
created: 2026-07-21 18:50
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-316`. Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 18:51
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 18:51
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 18:52
---
Agent completed successfully in 60s (446280 tokens)
---
author: oompah
created: 2026-07-21 18:52
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 8
- Tokens: 444.0K in / 2.3K out [446.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 0s
- Log: OOMPAH-316__20260721T185142Z.jsonl
---
author: oompah
created: 2026-07-21 18:52
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-316`. No stronger profile is configured; retrying with 'deep' in 20s (2/3).
---
author: oompah
created: 2026-07-21 18:53
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-21 18:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 18:54
---
Duplicate screening complete: no duplicate found.

Reviewed all tasks in .oompah/tasks/ (archived, done, backlog) for matches on: 'state_branch', 'exocomp', 'proj-c260b117', 'Fetch issues failed', 'state branch does not exist', fingerprint '9a803f3b8b56abc0'.

Closest candidate reviewed: OOMPAH-282 ('[backend:state_branch_migration] Stage A migration failed for project proj-edbc8b4c'). This is a different error (UnicodeEncodeError during Stage A migration for a different project), with a different fingerprint (9eaadc366ca8cc18). Not a duplicate.

OOMPAH-316 is a unique bug: when state_branch_enabled=True is set for a project but the state branch has never been bootstrapped, fetching issues raises an unhandled error instead of degrading gracefully.

Focus handoff: duplicate_detector
1. Outcome: No duplicate — this is a unique bug.
2. Relevant files: oompah/state_branch.py or similar fetch-issues code path that raises the error; plans/state-branch-design.md section on startup validation (§ startup checks when state_branch_enabled=True).
3. Remaining work: Find the fetch-issues code that raises 'State branch does not exist' and add graceful error handling (catch the exception, log a warning, fall back to non-state-branch read or surface a clear error, suppress the error_watcher trigger).
4. Recommended next focus: needs:feature (bug fix implementation)
---
author: oompah
created: 2026-07-21 18:55
---
Agent completed successfully in 131s (4233 tokens)
---
author: oompah
created: 2026-07-21 18:55
---
Run #3 [attempt=3, profile=deep, role=deep -> Claude/default]
- Turns: 36, Tool calls: 25
- Tokens: 19 in / 4.2K out [4.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 11s
- Log: OOMPAH-316__20260721T185308Z.jsonl
---
author: oompah
created: 2026-07-21 18:55
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 19:01
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 19:01
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-21 19:01
---
Understanding: I will trace the GitHub issue fetch/state-branch read path, identify why an unbootstrapped state branch escapes as an error, add focused handling and a regression test, then run the project test target and deliver the fix.
---
author: oompah
created: 2026-07-21 19:02
---
Discovery:  raises a generic  for a missing bootstrap branch.  catches it but logs , which error_watcher auto-files. I will introduce a dedicated missing-state-branch exception and downgrade only that expected configuration condition to an actionable warning; unrelated tracker failures remain error-level.
---
author: oompah
created: 2026-07-21 19:02
---
Discovery: the state-root setup raises a generic TrackerError for a missing bootstrap branch. The server catches it but logs ERROR, which error_watcher auto-files. I will introduce a dedicated missing-state-branch exception and downgrade only that expected configuration condition to an actionable warning; unrelated tracker failures remain error-level.
---
author: oompah
created: 2026-07-21 19:03
---
Implementation: added StateBranchMissingError for the precise unbootstrapped-state-branch condition. The multi-project issue fetcher now logs that exception as an actionable warning and returns no issues for only that project; all other TrackerError and ProjectError cases retain their existing error logging. Added regression tests for both log levels.
---
author: oompah
created: 2026-07-21 19:04
---
Verification: focused regression coverage passed: pytest tests/test_server_issue_snapshot.py tests/test_oompah_md_tracker_state_branch.py -v (47 passed). The required make test target was also attempted but could not start because uv failed to create a sandbox DBus transient scope before pytest ran. git diff --check and Python compilation passed.
---
author: oompah
created: 2026-07-21 19:04
---
Focus handoff: general

1. Outcome: Implemented and verified the missing-state-branch graceful-degradation fix locally.
2. Relevant files/evidence: oompah/oompah_md_tracker.py adds StateBranchMissingError; oompah/server.py logs only that condition at warning level while retaining error logging for all other tracker failures; tests/test_server_issue_snapshot.py and tests/test_oompah_md_tracker_state_branch.py cover both behaviors. Focused pytest result: 47 passed. make test could not start because sandboxed uv failed creating a DBus transient scope.
3. Remaining blocker: git add and commit cannot create /home/shedwards/.oompah/repos/oompah/.git/worktrees/OOMPAH-316/index.lock because that shared git directory is read-only in this agent sandbox. No commit or push is possible; local changes remain in this worktree.
4. Recommended next focus: devops, to restore write access to the worktree common git directory or provide a landing mechanism.
---
author: oompah
created: 2026-07-21 19:05
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/default]
- Turns: 0, Tool calls: 18
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 43s
- Log: OOMPAH-316__20260721T190147Z.jsonl
---
author: oompah
created: 2026-07-21 19:10
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 19:10
---
Focus: DevOps Engineer
---
author: oompah
created: 2026-07-21 19:11
---
Agent completed successfully in 95s (524123 tokens)
---
author: oompah
created: 2026-07-21 19:11
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 10
- Tokens: 520.9K in / 3.2K out [524.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 35s
- Log: OOMPAH-316__20260721T191018Z.jsonl
---
author: oompah
created: 2026-07-21 19:11
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-316`. No stronger profile is configured; retrying with 'deep' in 10s (1/3).
---
author: oompah
created: 2026-07-21 19:12
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 19:12
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->
