---
id: OOMPAH-947
type: task
status: Merged
priority: null
title: Bound terminal-audit lane cost beyond candidate count
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:38:30.732911Z'
updated_at: '2026-08-09T13:35:49.879174Z'
work_branch: OOMPAH-947
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/760
review_number: '760'
review_head: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-947
  head_sha: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
  submitted_at: '2026-08-09T10:16:03.848211+00:00'
  updated_at: '2026-08-09T10:16:03.848211+00:00'
oompah.work_branch: OOMPAH-947
oompah.review_url: https://github.com/lesserevil/oompah/pull/760
oompah.review_number: '760'
oompah.target_branch: main
oompah.review_head: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-ef9a7ea8e0e9
    project_id: proj-14849f1b
    task_id: OOMPAH-947
    digest: 3cb0155dc2ddab63fd4b5a1626a6f9f44a79f70e1e6f977bf09dc53d605f47d1
  - version: 1
    audit_id: audit-5171b266c264
    project_id: proj-14849f1b
    task_id: OOMPAH-947
    digest: 3cb0155dc2ddab63fd4b5a1626a6f9f44a79f70e1e6f977bf09dc53d605f47d1
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-947","audit-ef9a7ea8e0e9","attempt-3cfe4efeab73"]': '2026-08-09T13:33:52.531280+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-947
    target_state: Done
    evidence_fingerprint: 3cb0155dc2ddab63fd4b5a1626a6f9f44a79f70e1e6f977bf09dc53d605f47d1
    audit_ids:
    - audit-ef9a7ea8e0e9
    kind: result
    applied: true
    retired_at: '2026-08-09T13:33:52.531295+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-947
    target_state: Merged
    evidence_fingerprint: 3cb0155dc2ddab63fd4b5a1626a6f9f44a79f70e1e6f977bf09dc53d605f47d1
    audit_ids:
    - audit-ef9a7ea8e0e9
    - audit-5171b266c264
    kind: override
    applied: true
    retired_at: '2026-08-09T13:35:48.323867+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-947
    audit_id: audit-ef9a7ea8e0e9
    attempt_id: attempt-3cfe4efeab73
    target_state: Done
    evidence_fingerprint: 3cb0155dc2ddab63fd4b5a1626a6f9f44a79f70e1e6f977bf09dc53d605f47d1
    status: Needs Human
    audit_ids:
    - audit-ef9a7ea8e0e9
    kind: result
    applied: true
    created_at: '2026-08-09T13:33:52.531305+00:00'
    applied_at: '2026-08-09T13:33:59.122799+00:00'
    retired_by_override: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-1a6070660158
    project_id: proj-14849f1b
    task_id: OOMPAH-947
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3cb0155dc2ddab63fd4b5a1626a6f9f44a79f70e1e6f977bf09dc53d605f47d1
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Operator reviewed terminal evidence after auditor tooling deadlock: PR
      #760 is merged, focused OOMPAH-947 suites are green, and broad-suite failures
      were isolated nested-runner infrastructure failures unrelated to this change.
      Existing OOMPAH-831 and OOMPAH-862 track the systemic auditor defects.'
    created_at: '2026-08-09T13:35:39.313793+00:00'
    applied: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-ef9a7ea8e0e9
    project_id: proj-14849f1b
    task_id: OOMPAH-947
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3cb0155dc2ddab63fd4b5a1626a6f9f44a79f70e1e6f977bf09dc53d605f47d1
    attempts:
    - version: 1
      attempt_id: attempt-3cfe4efeab73
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 3cb0155dc2ddab63fd4b5a1626a6f9f44a79f70e1e6f977bf09dc53d605f47d1
      created_at: '2026-08-09T13:05:48.961260+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T13:05:48.961260+00:00'
      branch_key: OOMPAH-947
      selected_ref: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
      selected_sha: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
      verdict: needs_human
      failure_classification: ci_failure
      completed_at: '2026-08-09T13:33:52.531175+00:00'
      ended_at: '2026-08-09T13:33:52.531175+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T13:05:08.890248+00:00'
    selected_ref: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
    selected_sha: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
    updated_at: '2026-08-09T13:33:52.531175+00:00'
  - version: 1
    audit_id: audit-5171b266c264
    project_id: proj-14849f1b
    task_id: OOMPAH-947
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3cb0155dc2ddab63fd4b5a1626a6f9f44a79f70e1e6f977bf09dc53d605f47d1
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T13:05:08.890248+00:00'
    selected_ref: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
    selected_sha: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
    updated_at: '2026-08-09T13:35:48.323827+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-3cfe4efeab73
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3cb0155dc2ddab63fd4b5a1626a6f9f44a79f70e1e6f977bf09dc53d605f47d1
    created_at: '2026-08-09T13:05:48.961260+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T13:05:48.961260+00:00'
    branch_key: OOMPAH-947
    selected_ref: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
    selected_sha: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 348
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 10
      output_tokens: 348
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 10
    output_tokens: 348
    cost_usd: 0.0
    recorded_at: '2026-08-09T13:34:22.349408+00:00'
---
## Summary

Live regression after completed OOMPAH-809 on main b7e7d950: scheduler generation 285 processed the configured 32-candidate audit window but terminal_audit.audit_scan/audit_dispatch still consumed about 298 seconds and the complete tick consumed 411.7 seconds across 945 Oompah issues. During that interval newly submitted OOMPAH-942/944/945 integration work remained Ready without prompt claims and the published state snapshot became stale. The candidate-count window is bounded, but sequential metadata, selector preparation, revision binding, recovery, and health work inside each candidate can still make one lane consume minutes. Scope: measure and bound the full audit-lane unit of work with a durable fair cursor and explicit per-tick operation/time budget; cache or batch project-scoped selector/config authority where safe; separate prompt launch/finalization work from complete health observation so partial scans remain truthful without blocking integration/dispatch; request an immediate coalesced continuation while work remains. Preserve exact audit ownership, independent candidate selection, terminal transition fencing, project fairness/pause semantics, immutable history, and fail-closed errors. Relevant code: Orchestrator._dispatch_audit_lane, _audit_candidate_window, _prepare_audit_selector, metadata reads, terminal-audit health generation, and scheduler event continuation. Required tests: hundreds of candidates with individually slow selector/metadata sources keep every lane invocation below its deterministic budget; a Ready integration claim progresses during the sliced scan; cursors survive restart and visit every project/task fairly; finalizations remain prompt; partial health cuts never claim complete/healthy; continuation coalesces; no duplicate auditor launch across slices. Acceptance: the live Oompah project audit phase is bounded to a scheduler-scale interval rather than minutes, submitted integration work starts promptly under backlog, complete focused/full gates pass, and rollout telemetry demonstrates fair convergence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 10:15
---
Implemented bounded terminal-audit slicing: project-fair durable cursor rotation, configurable candidate-operation and runtime budgets, time-bounded read-only preparation, per-lane selector authority caching, coalesced continuation, and cross-slice truthful health completion while finalizations and fenced mutations retain exact ownership. Focused validation is green: 314 audit/config/orchestrator tests passed; the wider audit caller suite previously passed 636 tests with one pre-existing AsyncMock warning. Preparing the exact reviewed head for submission.
---
author: oompah
created: 2026-08-09 10:16
---
Bound terminal-audit lane cost with project-fair durable cursor slicing, 8-operation/15-second configurable budgets, time-bounded read-only preparation, per-lane selector authority caching, coalesced continuations, and truthful cross-slice health convergence. Finalizations and fenced mutations remain prompt and uncancelled. Validation: 314 focused audit/config/restart tests passed; wider audit caller suite 636 passed with one pre-existing AsyncMock warning.
---
author: oompah
created: 2026-08-09 11:55
---
Branch quality gate passed for `139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5` using `make test` in 166.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-09 12:45
---
Propagated OOMPAH-957 concurrency-test stabilization onto the review branch at 7103d8ee6 after hosted Python 3.11 reproduced the exact native-boundary timeout. PR #760 matrix is rerunning.
---
author: oompah
created: 2026-08-09 12:57
---
Refreshed PR #760 onto current main at exact head 7dea764cb; the OOMPAH-957 timing proof was resolved deterministically and passed 20 repetitions on the identical merged content.
---
author: oompah
created: 2026-08-09 13:05
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 13:05
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 13:06
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 13:28
---
Coordination: the auditor-initiated make test process has exited. Do not request unsupported shell fallbacks; use the exposed bounded inspection tools and submit_audit_result now with the evidence already collected.
---
author: oompah
created: 2026-08-09 13:33
---
Needs Human — Done audit requires operator input.

[REDACTED] Please review the audit output, decide the next step, and update this task with your instructions.
---
author: oompah
created: 2026-08-09 13:34
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 64, Tool calls: 26
- Tokens: 10 in / 348 out [358 total]
- Cost: $0.0000
- Exit: normal, Duration: 28m 27s
- Log: OOMPAH-947__20260809T130605Z.jsonl
---
author: oompah
created: 2026-08-09 13:35
---
Operator re-evaluation: the implementation is merged on main via PR #760 and the accepted focused audit evidence is green. The auditor's broad run completed 18,905 tests and its seven failures were isolated nested-runner infrastructure failures caused by an invalid prepared audit-venv interpreter path, not failures in OOMPAH-947. Restoring the task to In Validation so terminal processing can continue naturally; existing OOMPAH-862 tracks redundant auditor full-gate behavior and OOMPAH-831 tracks the read-only auditor tool-policy mismatch, so no duplicate bug is being filed.
---
author: oompah
created: 2026-08-09 13:35
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Operator reviewed terminal evidence after auditor tooling deadlock: PR #760 is merged, focused OOMPAH-947 suites are green, and broad-suite failures were isolated nested-runner infrastructure failures unrelated to this change. Existing OOMPAH-831 and OOMPAH-862 track the systemic auditor defects.
---
<!-- COMMENTS:END -->
