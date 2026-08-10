---
id: OOMPAH-985
type: task
status: Merged
priority: null
title: Make backlog refresh retry proof wait for exact completion
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T04:20:13.834988Z'
updated_at: '2026-08-10T05:47:06.559522Z'
work_branch: OOMPAH-985
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-985
  head_sha: 2a255c5c0d2f8d9850c4135809422c33f9409571
  submitted_at: '2026-08-10T05:37:01.036213+00:00'
  updated_at: '2026-08-10T05:37:01.036213+00:00'
oompah.work_branch: OOMPAH-985
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-e0ba7923c746
    project_id: proj-14849f1b
    task_id: OOMPAH-985
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a867cb0ccf3fd7ad055b872f68d606f0372bdb68727259a42a922eff3b225c0f
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: '[REDACTED]'
    created_at: '2026-08-10T05:46:55.571267+00:00'
    selected_ref: 2a255c5c0d2f8d9850c4135809422c33f9409571
    selected_sha: 2a255c5c0d2f8d9850c4135809422c33f9409571
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-985
    target_state: Merged
    evidence_fingerprint: a867cb0ccf3fd7ad055b872f68d606f0372bdb68727259a42a922eff3b225c0f
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-10T05:47:05.035074+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by OOMPAH-984 protected PR #792, GitHub Actions run 31354670866, Python 3.11 job 93352055381. tests/test_release_delivery_refresh.py::TestRefreshManagerTriggerRefresh::test_trigger_refresh_after_failure_is_retry failed because it sleeps 0.05 seconds and then assumes the background refresh has reached failed; under loaded CI it was still loading_merged. OOMPAH-703 previously repaired adjacent invalidation tests but this retry path retained arbitrary wall-clock sleeps. Scope: replace both failure and successful-retry sleeps in this proof with BacklogRefreshManager's exact completion/lifecycle synchronization, changing production code only if the existing public completion seam cannot distinguish generations; do not widen delays. Relevant files: tests/test_release_delivery_refresh.py and narrowly oompah/release_delivery_refresh.py if required. Required tests: repeated focused runs on Python 3.11 under load, complete release-delivery-refresh suite, Python 3.12/3.13 focused compatibility, Ruff/diff checks. Acceptance: the test deterministically proves an initial failed generation reaches failed, trigger_refresh starts a distinct retry generation, and the retry reaches complete with the expected result; no scheduler timing assumption remains and protected CI passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 04:28
---
Implemented and pushed exact refresh-generation synchronization at 2a255c5c0d2f8d9850c4135809422c33f9409571. The retry test now awaits BacklogRefreshManager.wait_for_completion for both the failing generation and the distinct successful retry, asserting terminal phase/error/result timestamp, exact cached result identity, and one call per service; no arbitrary sleeps, timeout widening, or production changes. Validation: Python 3.11 focused 51/51 plus full tests/test_release_delivery_refresh.py 55 passed; Python 3.12 full file 55 passed; Python 3.13 focused 26/26 plus full file 55 passed; independent review added 100 focused repetitions and approved; git diff --check clean; Ruff introduced no new findings versus the existing file baseline. Deliberate delivery plan: keep OOMPAH-985 claimed and unsubmitted while OOMPAH-984 / PR #792 is rebased onto this exact commit so one combined CI run validates both flake fixes. After PR #792 lands, submit this exact contained commit through the supported already-landed path.
---
author: oompah
created: 2026-08-10 05:37
---
Exact head 2a255c5c0d2f8d9850c4135809422c33f9409571 is contained in merged OOMPAH-984 PR #792 / main merge 148db44a97e42140160a428bd11eed2c50f75381. Combined exact-head make test passed 19,279 tests plus protected Python 3.11/3.12/3.13 CI; submit through the supported already-landed path.
---
author: oompah
created: 2026-08-10 05:47
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: [REDACTED]
---
<!-- COMMENTS:END -->
