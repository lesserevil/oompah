---
id: OOMPAH-704
type: bug
status: Ready to Integrate
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
updated_at: '2026-08-02T21:29:54.954494Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
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
<!-- COMMENTS:END -->
