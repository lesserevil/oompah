---
id: OOMPAH-265
type: bug
status: In Progress
priority: 2
title: "[backend:server] Create issue API error: git push origin HEAD:main failed:\
  \ remote: Bypassed rule violations for refs/heads/main:        \nremote: \nremote:\
  \ - 3 of 3 required status checks are expecte..."
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-20T16:48:39.964670Z'
updated_at: '2026-07-20T17:04:55.982208Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#451
  owner: lesserevil
  repo: oompah
  number: '451'
  url: https://github.com/lesserevil/oompah/issues/451
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-20T16:58:18.928913+00:00'
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
  last_validated_at: '2026-07-20T16:48:52.593601+00:00'
oompah.agent_run_id: 8dd35186-923f-4358-865c-c3fa074f4dbc
oompah.task_costs:
  total_input_tokens: 67668
  total_output_tokens: 9965
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 67668
      output_tokens: 9965
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 27
    output_tokens: 9413
    cost_usd: 0.0
    recorded_at: '2026-07-20T17:01:28.917501+00:00'
  - profile: default
    model: unknown
    input_tokens: 67641
    output_tokens: 552
    cost_usd: 0.0
    recorded_at: '2026-07-20T17:03:42.883206+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:server`:

> Create issue API error: git push origin HEAD:main failed: remote: Bypassed rule violations for refs/heads/main:        
remote: 
remote: - 3 of 3 required status checks are expected.        
remote: 
To https://github.com/lesserevil/oompah.git
 ! [remote rejected]   HEAD -> main (cannot lock ref 'refs/heads/main': is at 0a970ee6253d1705ec68ed6b2d8b67b34abc90f6 but expected 5ff1a2f5dc54b652b570b5ba9753f4b854334998)
error: failed to push some refs to 'https://github.com/lesserevil/oompah.git'

### Desired Behavior

The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Create issue API error: git push origin HEAD:main failed: remote: Bypassed rule violations for refs/heads/main:        
remote: 
remote: - 3 of 3 required status checks are expected.        
remote: 
To https://github.com/lesserevil/oompah.git
 ! [remote rejected]   HEAD -> main (cannot lock ref 'refs/heads/main': is at 0a970ee6253d1705ec68ed6b2d8b67b34abc90f6 but expected 5ff1a2f5dc54b652b570b5ba9753f4b854334998)
error: failed to push some refs to 'https://github.com/lesserevil/oompah.git'

### Acceptance Criteria

- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: d5eadc888bec39d3
- dedup_fingerprint: d5eadc888bec39d3
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/451
- Requestor: @NVShawn
- Reference: lesserevil/oompah#451

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 16:55
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 16:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 16:56
---
Understanding: This issue is an auto-filed error from oompah's error_watcher. The root error is that a 'git push origin HEAD:main' failed due to GitHub branch protection rules (3 of 3 required status checks not met, and the ref lock conflict). My role here is Duplicate Investigator — I need to determine if this is a duplicate of an existing issue before any implementation work begins. Searching now for similar tasks.
---
author: oompah
created: 2026-07-20 17:00
---
Discovery: Duplicate screening complete — OOMPAH-265 is NOT a duplicate.

**Error in OOMPAH-265:** git push origin HEAD:main failed with remote ref lock conflict: 'cannot lock ref refs/heads/main: is at 0a970ee6 but expected 5ff1a2f5'. This is a push-race where GitHub rejected the push because another concurrent push arrived between oompah's fetch and push. The 'Bypassed rule violations' text is an informational GitHub message about branch protection, not the actual failure cause.

**Closest reviewed tasks:**

1. OOMPAH-235 (Done, 2026-07-18, commit fdd61e4a): Implemented push-race recovery in _commit_and_push() — after a rejected push, fetch/rebase and retry once. This IS the fix that was intended to handle OOMPAH-265's scenario. But OOMPAH-265 occurred 2026-07-20, two days after OOMPAH-235's fix, meaning the retry-once logic ran but the retry push ALSO failed (a second concurrent push beat oompah between the sync and the retry).

2. OOMPAH-204 (Merged): Added rebase fallback in _sync_from_remote() for diverged branch.

3. OOMPAH-233 (Merged): Added reset --hard fallback when both ff-only and rebase fail (later superseded by OOMPAH-235 which removed reset --hard).

**Root cause of OOMPAH-265:** In _commit_and_push() (oompah/oompah_md_tracker.py:1055-1060), the single retry is insufficient when three or more concurrent tracker writers race. After the first push fails (check=False) and _sync_from_remote runs, the retry push (check=True) also fails because a second concurrent push arrived. TrackerError propagates and error_watcher files this task.

**Distinct fingerprint:** d5eadc888bec39d3 appears only in OOMPAH-265. No other tasks describe this exact failure path. Not a duplicate.

**Recommended fix:** Add a retry loop (e.g. 3 attempts with exponential backoff or immediate re-sync) in _commit_and_push() rather than the current single retry, OR catch the TrackerError from the retry push, log a warning, and suppress it from error_watcher for known push-race failures.
---
author: oompah
created: 2026-07-20 17:01
---
Agent completed successfully in 375s (9440 tokens)
---
author: oompah
created: 2026-07-20 17:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 58, Tool calls: 43
- Tokens: 27 in / 9.4K out [9.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 15s
- Log: OOMPAH-265__20260720T165531Z.jsonl
---
author: oompah
created: 2026-07-20 17:01
---
Focus handoff required before leaving `duplicate_detector`. Add a comment headed `Focus handoff: duplicate_detector` with outcome, evidence, remaining work, and next focus.
---
author: oompah
created: 2026-07-20 17:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 17:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 17:03
---
Agent completed successfully in 69s (68193 tokens)
---
author: oompah
created: 2026-07-20 17:03
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 67.6K in / 552 out [68.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 9s
- Log: OOMPAH-265__20260720T170241Z.jsonl
---
author: oompah
created: 2026-07-20 17:03
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-265`. Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-20 17:04
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-20 17:04
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
