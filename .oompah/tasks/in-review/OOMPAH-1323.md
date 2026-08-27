---
id: OOMPAH-1323
type: bug
status: In Review
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1256 identifier=OOMPAH-1256 run_id=69f4a7d3905b4d3e801bc7f836234ea0
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T01:18:43.804044Z'
updated_at: '2026-08-27T03:31:17.672924Z'
work_branch: OOMPAH-1323
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/954
review_number: '954'
review_head: cf6ed93516203d684c7c9ca33259e4cf16f10e3e
merged_at: null
oompah.lifecycle_revision: 27
oompah.last_batch:
  batch_id: batch-6721ed37af5c4e51ae3558e98f499304
  actor: shedwards
  committed_at: '2026-08-21T01:29:59.950511Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f300b9d30de2ec5c81f04540a41a2149b66c00aeef3704035e67be8069232cc4
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T05:10:13.357549+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: No active (non-terminal) peer task in the provided corpus matches the
    specific `backend:orchestrator` pre-provider bounded task-authority deadline evidence
    timeout symptom; the closest reviewed items are terminal-audit enforcement fan-out/compatibility
    incidents (e.g., OOMPAH-1015) and earlier general orchestrator/workflow authority
    fixes (OOMPAH-1002/1001/1008), but their components and error signatures differ
    and none are active duplicates.

    Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: No active (non-terminal) peer task in the provided corpus matches the
    specific `backend:orchestrator` pre-provider bounded task-authority deadline evidence
    timeout symptom; the closest reviewed items are terminal-audit enforcement fan-out/compatibility
    incidents (e.g., OOMPAH-1015) and earlier general orchestrator/workflow authority
    fixes (OOMPAH-1002/1001/1008), but their components and error signatures differ
    and none are active duplicates.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: 2f43676d360e41b8a978c41ec30576fe--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1323
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T05:10:13.362120+00:00'
  - run_id: cd531fd577b94af488dc62abbd215ed8--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1323
    source_sha: null
    completed_at: ''
  - run_id: 8f15dbfb124f4982a0b98806df4d2330--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1323
    source_sha: null
    completed_at: ''
  - run_id: 22d98792882a431daaf52ad3604e18fa--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: general
    source_branch: OOMPAH-1323
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T11:30:36.777204+00:00'
oompah.task_costs:
  total_input_tokens: 32478
  total_output_tokens: 162
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 32478
      output_tokens: 162
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 32104
    output_tokens: 121
    cost_usd: 0.0
    recorded_at: '2026-08-21T05:10:13.356820+00:00'
  - profile: default
    model: haiku
    input_tokens: 374
    output_tokens: 41
    cost_usd: 0.0
    recorded_at: '2026-08-21T11:30:36.771522+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1323
  base_branch: main
  base_sha: b149dbc8aafc583f248d223a176ba1c4817323c7
  head_sha: cf6ed93516203d684c7c9ca33259e4cf16f10e3e
  submitted_at: '2026-08-24T23:58:25.643633+00:00'
  updated_at: '2026-08-26T07:14:16.615493+00:00'
oompah.work_branch: OOMPAH-1323
oompah.review_url: https://github.com/lesserevil/oompah/pull/954
oompah.review_number: '954'
oompah.target_branch: main
oompah.review_head: cf6ed93516203d684c7c9ca33259e4cf16f10e3e
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-b4f5e9525b03
    project_id: proj-14849f1b
    task_id: OOMPAH-1323
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0f35b87c53445b19284d64eebc946f6f181c9a1a569582ae81735c301f6fa649
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Superseded by fixes already merged to main: production now uses a 60-second
      contributor-evidence persistence timeout, logs the expected bounded timeout
      at DEBUG, and excludes expected pre-provider retirement from error intake. The
      stale branch conflicts with newer recovery work and must not be rebased or merged.'
    created_at: '2026-08-27T03:31:16.173012+00:00'
    selected_ref: cf6ed93516203d684c7c9ca33259e4cf16f10e3e
    selected_sha: cf6ed93516203d684c7c9ca33259e4cf16f10e3e
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1256 identifier=OOMPAH-1256 run_id=69f4a7d3905b4d3e801bc7f836234ea0 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1256 identifier=OOMPAH-1256 run_id=69f4a7d3905b4d3e801bc7f836234ea0 timeout_seconds=5.0

### Expected Behavior
The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 7fb11d7065320387
- dedup_fingerprint: 7fb11d7065320387

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 05:09
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 05:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 05:10
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 32.1K in / 121 out [40.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 36s
- Log: OOMPAH-1323__20260821T050958Z.jsonl
---
author: oompah
created: 2026-08-21 09:53
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 09:53
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 09:54
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 57s
- Log: OOMPAH-1323__20260821T095328Z.jsonl
---
author: oompah
created: 2026-08-21 10:33
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 10:34
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 10:34
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 58s
- Log: OOMPAH-1323__20260821T103423Z.jsonl
---
author: oompah
created: 2026-08-21 11:22
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 11:23
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 11:23
---
Understanding: The normal pre-provider contributor-evidence deadline is being emitted at error severity and auto-filed. I will trace the deadline path and error watcher, make timeout degradation explicit/non-error without masking unrelated errors, add regression coverage, and run focused checks.
---
author: oompah
created: 2026-08-21 11:27
---
Discovery: _stage_work_contributor_launch intentionally retires the runtime for retry when the bounded evidence write times out, but uniquely logs that expected degradation at ERROR; error_watcher captures every oompah ERROR. Adjacent settling/cancellation paths use WARNING. The minimal fix is severity demotion with a regression assertion; existing unrelated auditor-rotation worktree changes will be preserved.
---
author: oompah
created: 2026-08-21 11:27
---
Implementation: Changed the expected contributor-evidence deadline retirement diagnostic from ERROR to WARNING, preserving its structured retirement metadata and actionable return. Extended the existing timeout regression to assert the diagnostic is emitted exactly once at WARNING, below error_watcher's ERROR threshold.
---
author: oompah
created: 2026-08-21 11:28
---
Verification: Focused timeout regressions passed (2/2), the full provider-retirement suite passed (21/21), both error_watcher suites passed (137/137), and git diff --check passed. This confirms expected timeout degradation remains functional and unrelated ERROR reporting coverage is intact.
---
author: oompah
created: 2026-08-21 11:29
---
Completion: Delivered and pushed commit dccf429d6. Normal bounded contributor-evidence timeout retirement now logs at WARNING (so error_watcher does not auto-file it), with regression coverage for exact severity; focused retirement and error_watcher suites all pass. Unrelated pre-existing auditor-rotation working-tree edits were intentionally excluded from the commit.
---
author: oompah
created: 2026-08-21 11:29
---
Demoted expected pre-provider contributor-evidence timeout retirement from ERROR to WARNING and added severity regression coverage; focused provider-retirement and error_watcher tests pass.
---
author: oompah
created: 2026-08-21 11:30
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 34, Tool calls: 34
- Tokens: 374 in / 41 out [36.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 8m 9s
- Log: OOMPAH-1323__20260821T112342Z.jsonl
---
author: oompah
created: 2026-08-24 23:58
---
Resubmitted the current clean pushed branch head after workflow liveness detected that the prior submission head was stale.
---
author: oompah
created: 2026-08-26 05:28
---
Branch quality gate passed for `cf6ed93516203d684c7c9ca33259e4cf16f10e3e` using `make test` in 184.9s. Review creation may proceed.
---
author: oompah
created: 2026-08-26 08:04
---
Branch quality gate passed for `cf6ed93516203d684c7c9ca33259e4cf16f10e3e` using `make test` in 183.0s. Review creation may proceed.
---
<!-- COMMENTS:END -->
