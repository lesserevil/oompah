---
id: OOMPAH-981
type: bug
status: Merged
priority: 1
title: Route post-landing epic follow-ups to the live target branch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T02:42:39.740073Z'
updated_at: '2026-08-10T05:15:24.129175Z'
work_branch: OOMPAH-981
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/793
review_number: '793'
review_head: ca2a1dc03822a181b57f153f60bbff851004d061
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-981
  head_sha: ca2a1dc03822a181b57f153f60bbff851004d061
  submitted_at: '2026-08-10T04:03:44.129514+00:00'
  updated_at: '2026-08-10T04:03:44.129514+00:00'
oompah.work_branch: OOMPAH-981
oompah.review_url: https://github.com/lesserevil/oompah/pull/793
oompah.review_number: '793'
oompah.target_branch: main
oompah.review_head: ca2a1dc03822a181b57f153f60bbff851004d061
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-dd2821494e7f
    project_id: proj-14849f1b
    task_id: OOMPAH-981
    digest: ae2e30ef3c71bc135ddebea0aac3b0eed37fe1cb534fa7d0517c3d9d8bf52c85
  - version: 1
    audit_id: audit-b2fe39e75f67
    project_id: proj-14849f1b
    task_id: OOMPAH-981
    digest: ae2e30ef3c71bc135ddebea0aac3b0eed37fe1cb534fa7d0517c3d9d8bf52c85
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-981","audit-dd2821494e7f","attempt-b542f1861b7f"]': '2026-08-10T05:04:52.603734+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-981
    target_state: Done
    evidence_fingerprint: ae2e30ef3c71bc135ddebea0aac3b0eed37fe1cb534fa7d0517c3d9d8bf52c85
    audit_ids:
    - audit-dd2821494e7f
    kind: result
    applied: true
    retired_at: '2026-08-10T05:04:52.603754+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-981
    target_state: Merged
    evidence_fingerprint: ae2e30ef3c71bc135ddebea0aac3b0eed37fe1cb534fa7d0517c3d9d8bf52c85
    audit_ids:
    - audit-dd2821494e7f
    - audit-b2fe39e75f67
    kind: override
    applied: true
    retired_at: '2026-08-10T05:15:22.632961+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-981
    audit_id: audit-dd2821494e7f
    attempt_id: attempt-b542f1861b7f
    target_state: Done
    evidence_fingerprint: ae2e30ef3c71bc135ddebea0aac3b0eed37fe1cb534fa7d0517c3d9d8bf52c85
    status: In Validation
    audit_ids:
    - audit-dd2821494e7f
    kind: result
    applied: true
    created_at: '2026-08-10T05:04:52.603766+00:00'
    applied_at: '2026-08-10T05:04:59.628211+00:00'
    retired_by_override: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-a78f41ff99b0
    project_id: proj-14849f1b
    task_id: OOMPAH-981
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ae2e30ef3c71bc135ddebea0aac3b0eed37fe1cb534fa7d0517c3d9d8bf52c85
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner terminal override after exact accepted head ca2a1dc03822a181b57f153f60bbff851004d061
      passed the authoritative branch gate, protected Python 3.11/3.12/3.13 CI, and
      an independent Done audit with 19,292 passing tests; PR #793 merged as 295df91c40f17a50ce6cf0d640c0667c48b469de
      and the exact head is contained in origin/main. The Merged-stage auditor entered
      the same redundant full-gate path already reproduced by OOMPAH-983; OOMPAH-988
      tracks the deployed gate-reuse regression.'
    created_at: '2026-08-10T05:15:13.085677+00:00'
    selected_ref: ca2a1dc03822a181b57f153f60bbff851004d061
    selected_sha: ca2a1dc03822a181b57f153f60bbff851004d061
    applied: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-dd2821494e7f
    project_id: proj-14849f1b
    task_id: OOMPAH-981
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ae2e30ef3c71bc135ddebea0aac3b0eed37fe1cb534fa7d0517c3d9d8bf52c85
    attempts:
    - version: 1
      attempt_id: attempt-b542f1861b7f
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: ae2e30ef3c71bc135ddebea0aac3b0eed37fe1cb534fa7d0517c3d9d8bf52c85
      created_at: '2026-08-10T04:40:59.117868+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-10T04:40:59.117868+00:00'
      branch_key: OOMPAH-981
      selected_ref: ca2a1dc03822a181b57f153f60bbff851004d061
      selected_sha: ca2a1dc03822a181b57f153f60bbff851004d061
      verdict: pass
      completed_at: '2026-08-10T05:04:52.603586+00:00'
      ended_at: '2026-08-10T05:04:52.603586+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-10T04:40:15.636623+00:00'
    selected_ref: ca2a1dc03822a181b57f153f60bbff851004d061
    selected_sha: ca2a1dc03822a181b57f153f60bbff851004d061
    updated_at: '2026-08-10T05:04:52.603586+00:00'
  - version: 1
    audit_id: audit-b2fe39e75f67
    project_id: proj-14849f1b
    task_id: OOMPAH-981
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ae2e30ef3c71bc135ddebea0aac3b0eed37fe1cb534fa7d0517c3d9d8bf52c85
    attempts:
    - version: 1
      attempt_id: attempt-230097c6f6ff
      target_state: Merged
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: ae2e30ef3c71bc135ddebea0aac3b0eed37fe1cb534fa7d0517c3d9d8bf52c85
      created_at: '2026-08-10T05:13:23.288953+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-10T05:13:23.288953+00:00'
      branch_key: OOMPAH-981
      selected_ref: ca2a1dc03822a181b57f153f60bbff851004d061
      selected_sha: ca2a1dc03822a181b57f153f60bbff851004d061
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-10T04:40:15.636623+00:00'
    selected_ref: ca2a1dc03822a181b57f153f60bbff851004d061
    selected_sha: ca2a1dc03822a181b57f153f60bbff851004d061
    updated_at: '2026-08-10T05:15:22.632926+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-b542f1861b7f
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ae2e30ef3c71bc135ddebea0aac3b0eed37fe1cb534fa7d0517c3d9d8bf52c85
    created_at: '2026-08-10T04:40:59.117868+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-10T04:40:59.117868+00:00'
    branch_key: OOMPAH-981
    selected_ref: ca2a1dc03822a181b57f153f60bbff851004d061
    selected_sha: ca2a1dc03822a181b57f153f60bbff851004d061
  - version: 1
    attempt_id: attempt-230097c6f6ff
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ae2e30ef3c71bc135ddebea0aac3b0eed37fe1cb534fa7d0517c3d9d8bf52c85
    created_at: '2026-08-10T05:13:23.288953+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-10T05:13:23.288953+00:00'
    branch_key: OOMPAH-981
    selected_ref: ca2a1dc03822a181b57f153f60bbff851004d061
    selected_sha: ca2a1dc03822a181b57f153f60bbff851004d061
oompah.task_costs:
  total_input_tokens: 42
  total_output_tokens: 2193
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 42
      output_tokens: 2193
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 42
    output_tokens: 2193
    cost_usd: 0.0
    recorded_at: '2026-08-10T05:05:12.139862+00:00'
---
## Summary

Triggered by: OOMPAH-980

Triggered by OOMPAH-980 under already-landed epic OOMPAH-940. OOMPAH-940's reviewed epic branch had already merged to main, but submitting the newly created follow-up OOMPAH-980 still selected the stale epic-OOMPAH-940 base and routed mergeable direct-main work to Needs Rebase. Scope: resolve the effective integration target for a child created after its parent epic has authoritatively landed; route that follow-up to the current live target branch or a supported addendum/recovery lane without mutating or reusing the stale epic branch; preserve existing shared and nested active-epic routing, exact submitted-head authority, dependency ordering, and fail-closed behavior when landing evidence is absent or contradictory. Relevant code includes submit/integration target resolution, parent epic landing evidence, queue record creation, and direct-main reconciliation. Required tests: active shared-epic child still targets the epic branch; landed parent follow-up targets the current default or immediate target; parent-landing race; pruned/stale epic refs; nested epic target; exact submitted head; restart/idempotence; and an already merged direct-main PR reconciles without false Needs Rebase. Acceptance: an OOMPAH-980-shaped submission enters the correct live integration path without a manual PR, rebase workaround, or terminal override; focused tests and the complete project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 02:58
---
Forward invariant added from the live parent decision: a service-authorized post-landing standalone child must project its accepted task branch and live target into EpicFactCollector. Otherwise the already-landed parent remains blocked on the stale epic branch even after the child review lands. Regression coverage now includes that parent rollup flow as well as submit routing.
---
author: oompah
created: 2026-08-10 03:15
---
Direct-owner implementation remains active on branch OOMPAH-981. End-to-end post-parent landing routing is implemented and expanded race/restart/direct-delivery regressions are being completed before review. No product blocker is outstanding.
---
author: oompah
created: 2026-08-10 04:03
---
Implementation pushed at ca2a1dc03 on branch OOMPAH-981. Validation: 403 tests passed across standalone delivery, integration workflow, epic rollup, workflow facts, and work decisions; 441 tests passed across worker submission, task handoff, integration records, workflow runtime, and project-store coverage. Focused Ruff critical-error rules (E9,F63,F7,F82), py_compile, git diff --check, commit hooks, gitleaks, and paranoid secret scan passed. Independent race review approved the final issue→project→queue lock order, tracker-first bidirectional compensation, partial-write restart recovery, exact pre-forge route callback, and parent-safe no-op persistence with no remaining blockers.
---
author: oompah
created: 2026-08-10 04:03
---
Implemented exact routing for children submitted after an already-landed top-level or nested parent, with durable standalone authority, live-target rollup, tracker-first queue compensation, restart recovery, and forge/no-op race fences. Pushed ca2a1dc03; 844 affected tests and focused lint/checks pass; independent race review approved.
---
author: oompah
created: 2026-08-10 04:21
---
Branch quality gate passed for `ca2a1dc03822a181b57f153f60bbff851004d061` using `make test` in 168.5s. Review creation may proceed.
---
author: oompah
created: 2026-08-10 04:40
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-10 04:41
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-10 04:41
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-10 05:04
---
Audit PASS — Done

Full gate `make test` passed on accepted head ca2a1dc03822a181b57f153f60bbff851004d061: 19,292 tests passed, 7 skipped, 2 xfailed in 1243.47 seconds. No code quality issues detected. OOMPAH-981 implementation is complete and verified.

Safe evidence:
- test_results.total_passed: 19292
- test_results.total_skipped: 7
- test_results.total_xfailed: 2
- test_results.execution_time_seconds: 1243.47
- test_results.execution_time_formatted: 0:20:43
- validation_command: make test
- accepted_head_sha: ca2a1dc03822a181b57f153f60bbff851004d061
- audit_contract.audit_id: audit-dd2821494e7f
- audit_contract.target_state: Done
- audit_contract.evidence_fingerprint: ae2e30ef3c71bc135ddebea0aac3b0eed37fe1cb534fa7d0517c3d9d8bf52c85
---
author: oompah
created: 2026-08-10 05:05
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 14, Tool calls: 4
- Tokens: 42 in / 2.2K out [2.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 24m 10s
- Log: OOMPAH-981__20260810T044110Z.jsonl
---
author: oompah
created: 2026-08-10 05:13
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-10 05:13
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-10 05:15
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Project-owner terminal override after exact accepted head ca2a1dc03822a181b57f153f60bbff851004d061 passed the authoritative branch gate, protected Python 3.11/3.12/3.13 CI, and an independent Done audit with 19,292 passing tests; PR #793 merged as 295df91c40f17a50ce6cf0d640c0667c48b469de and the exact head is contained in origin/main. The Merged-stage auditor entered the same redundant full-gate path already reproduced by OOMPAH-983; OOMPAH-988 tracks the deployed gate-reuse regression.
---
<!-- COMMENTS:END -->
