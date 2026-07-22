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
assignee: null
created_at: '2026-07-21T23:24:47.554460Z'
updated_at: '2026-07-22T05:31:49.514032Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d4fb45b0-f72c-49e9-8eee-bd37699e0347
oompah.task_costs:
  total_input_tokens: 7529605
  total_output_tokens: 49557
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 7529605
      output_tokens: 49557
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 39
    output_tokens: 8551
    cost_usd: 0.0
    recorded_at: '2026-07-22T03:59:03.796886+00:00'
  - profile: standard
    model: unknown
    input_tokens: 588383
    output_tokens: 5123
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:01:12.443599+00:00'
  - profile: default
    model: unknown
    input_tokens: 840570
    output_tokens: 4659
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:05:00.930635+00:00'
  - profile: standard
    model: unknown
    input_tokens: 754112
    output_tokens: 4634
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:07:15.121663+00:00'
  - profile: deep
    model: unknown
    input_tokens: 842435
    output_tokens: 5080
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:09:49.938141+00:00'
  - profile: default
    model: unknown
    input_tokens: 305852
    output_tokens: 2192
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:35:44.693020+00:00'
  - profile: standard
    model: unknown
    input_tokens: 2346623
    output_tokens: 10845
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:40:53.660120+00:00'
  - profile: deep
    model: unknown
    input_tokens: 825071
    output_tokens: 4221
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:43:20.933094+00:00'
  - profile: default
    model: unknown
    input_tokens: 1026499
    output_tokens: 3964
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:01:19.473245+00:00'
  - profile: default
    model: unknown
    input_tokens: 21
    output_tokens: 288
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:27:07.979223+00:00'
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
author: oompah
created: 2026-07-22 03:59
---
Agent completed successfully in 415s (8590 tokens)
---
author: oompah
created: 2026-07-22 03:59
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 80, Tool calls: 58
- Tokens: 39 in / 8.6K out [8.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 55s
- Log: OOMPAH-339__20260722T035212Z.jsonl
---
author: oompah
created: 2026-07-22 03:59
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 03:59
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 03:59
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 04:01
---
Agent completed successfully in 116s (593506 tokens)
---
author: oompah
created: 2026-07-22 04:01
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 11
- Tokens: 588.4K in / 5.1K out [593.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 56s
- Log: OOMPAH-339__20260722T035919Z.jsonl
---
author: oompah
created: 2026-07-22 04:01
---
Agent completed without closing this issue (116s (593506 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 04:01
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-22 04:01
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 04:02
---
Agent completed successfully in 64s
---
author: oompah
created: 2026-07-22 04:02
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 7
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 4s
- Log: OOMPAH-339__20260722T040142Z.jsonl
---
author: oompah
created: 2026-07-22 04:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 04:03
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 04:05
---
Agent completed successfully in 117s (845229 tokens)
---
author: oompah
created: 2026-07-22 04:05
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 12
- Tokens: 840.6K in / 4.7K out [845.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 57s
- Log: OOMPAH-339__20260722T040306Z.jsonl
---
author: oompah
created: 2026-07-22 04:05
---
Agent completed without closing this issue (117s (845229 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 04:05
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 04:05
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 04:07
---
Agent completed successfully in 108s (758746 tokens)
---
author: oompah
created: 2026-07-22 04:07
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 11
- Tokens: 754.1K in / 4.6K out [758.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 48s
- Log: OOMPAH-339__20260722T040533Z.jsonl
---
author: oompah
created: 2026-07-22 04:07
---
Agent completed without closing this issue (108s (758746 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-22 04:07
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-22 04:07
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 04:09
---
Agent completed successfully in 128s (847515 tokens)
---
author: oompah
created: 2026-07-22 04:09
---
Run #3 [attempt=3, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 15
- Tokens: 842.4K in / 5.1K out [847.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 8s
- Log: OOMPAH-339__20260722T040743Z.jsonl
---
author: oompah
created: 2026-07-22 04:09
---
Agent completed 3 times without closing this issue. Human action required: review the agent run history and task state, then either close the task if the work is done or add specific guidance and move it back to Open.
---
author: oompah
created: 2026-07-22 04:33
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #1)

**State audited:** `Needs Human`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** Last agent comment signals completion without a human question; the Needs Human transition appears accidental.

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-07-22 04:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 04:34
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 04:35
---
Agent completed successfully in 64s (308044 tokens)
---
author: oompah
created: 2026-07-22 04:35
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 305.9K in / 2.2K out [308.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 4s
- Log: OOMPAH-339__20260722T043445Z.jsonl
---
author: oompah
created: 2026-07-22 04:35
---
Agent completed without closing this issue (64s (308044 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 04:36
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 04:36
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 04:40
---
Agent completed successfully in 292s (2357468 tokens)
---
author: oompah
created: 2026-07-22 04:40
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 30
- Tokens: 2.3M in / 10.8K out [2.4M total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 52s
- Log: OOMPAH-339__20260722T043603Z.jsonl
---
author: oompah
created: 2026-07-22 04:40
---
Agent completed without closing this issue (292s (2357468 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-22 04:41
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-22 04:41
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 04:43
---
Agent completed successfully in 119s (829292 tokens)
---
author: oompah
created: 2026-07-22 04:43
---
Run #3 [attempt=3, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 19
- Tokens: 825.1K in / 4.2K out [829.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 59s
- Log: OOMPAH-339__20260722T044126Z.jsonl
---
author: oompah
created: 2026-07-22 04:43
---
Agent completed 3 times without closing this issue. Human action required: review the agent run history and task state, then either close the task if the work is done or add specific guidance and move it back to Open.
---
author: user
created: 2026-07-22 04:48
---
There isn't enough information in the comments to tell why you are getting stuck. Try again, or decompose.
---
author: oompah
created: 2026-07-22 04:58
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 04:58
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 05:01
---
Agent completed successfully in 173s (1030463 tokens)
---
author: oompah
created: 2026-07-22 05:01
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 14
- Tokens: 1.0M in / 4.0K out [1.0M total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 53s
- Log: OOMPAH-339__20260722T045832Z.jsonl
---
author: oompah
created: 2026-07-22 05:01
---
Agent completed 4 times without closing this issue. Human action required: review the agent run history and task state, then either close the task if the work is done or add specific guidance and move it back to Open.
---
author: oompah
created: 2026-07-22 05:08
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #3)

**State audited:** `Needs Human`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** Last agent comment signals completion without a human question; the Needs Human transition appears accidental.

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-07-22 05:22
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:22
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 05:27
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 9
- Tokens: 21 in / 288 out [309 total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 19s
- Log: OOMPAH-339__20260722T052252Z.jsonl
---
author: oompah
created: 2026-07-22 05:27
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 05:27
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 05:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:30
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 05:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:31
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->
