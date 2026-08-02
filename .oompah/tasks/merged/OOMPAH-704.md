---
id: OOMPAH-704
type: bug
status: Merged
priority: 1
title: Fence graceful-restart redispatch against terminal state changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-02T21:11:44.479316Z'
updated_at: '2026-08-02T21:48:15.202869Z'
work_branch: OOMPAH-704
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/662
review_number: '662'
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-704
  head_sha: 5640fc49e3036e552d4c047c9c35b6509e94e8cd
  submitted_at: '2026-08-02T21:28:17.786334+00:00'
  updated_at: '2026-08-02T21:28:17.786334+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/662
oompah.review_number: '662'
oompah.work_branch: OOMPAH-704
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-6703e21dfb73
    project_id: proj-14849f1b
    task_id: OOMPAH-704
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5cef968f93c267a603a745502c8d66ca1838765281e77aee2271eec9296ec602
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'PR #662 merged at 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd; exact task
      head 5640fc49e3036e552d4c047c9c35b6509e94e8cd is contained in origin/main; GitHub
      CI passed on Python 3.11, 3.12, and 3.13; the server exact-head branch gate
      passed in 396.1s; local make test passed 15,010 tests with 7 skipped and 1 xfailed.
      Direct owner override avoids the known completion-auditor transport defect tracked
      by OOMPAH-701.'
    created_at: '2026-08-02T21:47:55.622824+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-704
    target_state: Merged
    evidence_fingerprint: 5cef968f93c267a603a745502c8d66ca1838765281e77aee2271eec9296ec602
    audit_ids:
    - audit-f9cc52ad4d0c
    - audit-7fee35fe24c0
    kind: override
    applied: true
    retired_at: '2026-08-02T21:48:00.904426+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f9cc52ad4d0c
    project_id: proj-14849f1b
    task_id: OOMPAH-704
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5cef968f93c267a603a745502c8d66ca1838765281e77aee2271eec9296ec602
    attempts:
    - version: 1
      attempt_id: attempt-1cf395ccc6ea
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 5cef968f93c267a603a745502c8d66ca1838765281e77aee2271eec9296ec602
      created_at: '2026-08-02T21:47:43.075909+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T21:47:43.075909+00:00'
      branch_key: OOMPAH-704
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T21:46:26.220743+00:00'
    updated_at: '2026-08-02T21:48:00.904380+00:00'
  - version: 1
    audit_id: audit-7fee35fe24c0
    project_id: proj-14849f1b
    task_id: OOMPAH-704
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5cef968f93c267a603a745502c8d66ca1838765281e77aee2271eec9296ec602
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T21:46:26.220743+00:00'
    updated_at: '2026-08-02T21:48:00.904406+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-1cf395ccc6ea
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5cef968f93c267a603a745502c8d66ca1838765281e77aee2271eec9296ec602
    created_at: '2026-08-02T21:47:43.075909+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T21:47:43.075909+00:00'
    branch_key: OOMPAH-704
oompah.task_costs:
  total_input_tokens: 12
  total_output_tokens: 2
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 12
      output_tokens: 2
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 12
    output_tokens: 2
    cost_usd: 0.0
    recorded_at: '2026-08-02T21:48:13.141156+00:00'
---
## Summary

Triggered by: OOMPAH-700

Production regression after OOMPAH-653: OOMPAH-700 was owner-overridden to Merged with audit override override-41c2b65a97e8 at 21:09, and an immediate task/state sweep confirmed Merged with zero pending audits. A concurrently running startup recovery then logged 'Marked OOMPAH-700 as Open for re-dispatch after restart' at 21:09:55 and regressed the terminal task to Open. Root cause is oompah/orchestrator.py::_recover_restart_issues, which loads restart_issues, clears the list, and unconditionally calls tracker.update_issue(identifier, status=OPEN) without re-reading canonical status or fencing against a terminal transition that commits after the restart snapshot was recorded. Implementation scope: make restart redispatch conditional and atomic with current task ownership/state; re-read canonical task state immediately before mutation; never reopen Merged, Archived, In Validation/terminal-audit-owned, or otherwise superseded work; preserve recovery for genuinely interrupted implementation tasks; consume stale restart records idempotently; integrate terminal audit/owner override generation or fingerprint fencing so an override concurrent with recovery always wins. Add deterministic barrier tests for an override landing after restart state load but before update, already-terminal restart records, audit-owned records, repeated startup recovery, and a normal interrupted In Progress task that should reopen exactly once. Acceptance criteria: the OOMPAH-700 sequence remains Merged across startup recovery; no terminal task can regress to Open; legitimate interrupted implementation work remains recoverable; focused orchestrator/terminal-audit tests, terminal mutation scan, and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 21:14
---
Second live symptom confirmed: replaying the exact owner override after the restart writer regressed OOMPAH-700 returned success with audit ID override-41c2b65a97e8 but left tracker status Open. In TerminalTransitionCoordinator._override_transition_locked, the applied-override idempotency return occurs before checking or repairing canonical tracker status. Extend scope: an identical applied override replay must verify current canonical status; if it has regressed, atomically reassert the recorded terminal target under the same ownership fence (or fail explicitly), retire sibling records again, and never report status remains Merged while the tracker is Open. Add a deterministic regression for this exact sequence.
---
author: oompah
created: 2026-08-02 21:14
---
Claimed for direct owner implementation; human-only prevents scheduler dispatch while the live recovery race is repaired.
---
author: oompah
created: 2026-08-02 21:19
---
Implemented the restart/override race repair in the task worktree. Restart recovery now acquires the shared per-task transition lock, re-reads canonical tracker state, and only reopens a genuine In Progress implementation; Merged, Archived, In Validation, Needs Human, Open, and unavailable states are never overwritten. Applied owner-override replay now refreshes tracker state and reasserts its already-authorized terminal target if a stale writer regressed it, without adding another override record. Deterministic focused coverage: 8 new/targeted tests passed; broader event-loop, terminal coordinator, override, and enforcement suites: 250 passed.
---
author: oompah
created: 2026-08-02 21:28
---
Fenced graceful-restart redispatch against newer terminal/audit state and made idempotent owner overrides repair regressed tracker status. Focused restart/terminal suites: 250 passed. Complete make test: 15,010 passed, 7 skipped, 1 xfailed. make check-secrets and git diff --check passed.
---
author: oompah
created: 2026-08-02 21:28
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-704`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `infrastructure_error`

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Candidate CI was not run because the submitted review branch tip is unavailable in the managed repository.
```
---
author: oompah
created: 2026-08-02 21:29
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-704`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `infrastructure_error`

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Candidate CI was not run because the submitted review branch tip is unavailable in the managed repository.
```
---
author: oompah
created: 2026-08-02 21:29
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-704`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `infrastructure_error`

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Candidate CI was not run because the submitted review branch tip is unavailable in the managed repository.
```
---
author: oompah
created: 2026-08-02 21:30
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-704`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `infrastructure_error`

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Candidate CI was not run because the submitted review branch tip is unavailable in the managed repository.
```
---
author: oompah
created: 2026-08-02 21:37
---
Branch quality gate passed for `5640fc49e3036e552d4c047c9c35b6509e94e8cd` using `make test` in 396.1s. Review creation may proceed.
---
author: oompah
created: 2026-08-02 21:46
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-02 21:46
---
YOLO: merged PR #662.
---
author: oompah
created: 2026-08-02 21:47
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 21:47
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 21:47
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: PR #662 merged at 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd; exact task head 5640fc49e3036e552d4c047c9c35b6509e94e8cd is contained in origin/main; GitHub CI passed on Python 3.11, 3.12, and 3.13; the server exact-head branch gate passed in 396.1s; local make test passed 15,010 tests with 7 skipped and 1 xfailed. Direct owner override avoids the known completion-auditor transport defect tracked by OOMPAH-701.
---
author: oompah
created: 2026-08-02 21:48
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 2, Tool calls: 1
- Tokens: 12 in / 2 out [14 total]
- Cost: $0.0000
- Exit: terminated, Duration: 29s
- Log: OOMPAH-704__20260802T214749Z.jsonl
---
<!-- COMMENTS:END -->
