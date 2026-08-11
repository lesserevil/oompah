---
id: OOMPAH-1082
type: task
status: In Validation
priority: null
title: Wake and age chained terminal-audit stages only after prerequisites become
  eligible
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T11:08:16.081490Z'
updated_at: '2026-08-11T12:37:53.069180Z'
work_branch: OOMPAH-1082
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/819
review_number: '819'
review_head: 4af4260085204071f14689771609658fb52329e1
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 874ac2f5-239e-4a7e-9442-06875ae3cd57
  request_fingerprint: 598acece51eff7c2be5431e6f95b016bb819341113c8f2b0b2f3fd89a5d1c05d
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1082
  base_branch: main
  base_sha: 712309b8179036474e40c5fd26f7d2b3c2a4b9b0
  head_sha: 4af4260085204071f14689771609658fb52329e1
  submitted_at: '2026-08-11T12:17:04.041362+00:00'
  updated_at: '2026-08-11T12:17:04.041362+00:00'
oompah.work_branch: OOMPAH-1082
oompah.review_url: https://github.com/lesserevil/oompah/pull/819
oompah.review_number: '819'
oompah.target_branch: main
oompah.review_head: 4af4260085204071f14689771609658fb52329e1
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-9193cb8ddfd6
    project_id: proj-14849f1b
    task_id: OOMPAH-1082
    digest: 9b2b997b620044ccd53da6072f11e1fdd456545a48d5d643f416f256730dc3dc
  - version: 1
    audit_id: audit-a54c56f04b36
    project_id: proj-14849f1b
    task_id: OOMPAH-1082
    digest: 9b2b997b620044ccd53da6072f11e1fdd456545a48d5d643f416f256730dc3dc
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1082","audit-9193cb8ddfd6","attempt-b707ed02a354"]': '2026-08-11T12:37:31.504266+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1082
    target_state: Done
    evidence_fingerprint: 9b2b997b620044ccd53da6072f11e1fdd456545a48d5d643f416f256730dc3dc
    workflow_revision: null
    selected_ref: 4af4260085204071f14689771609658fb52329e1
    selected_sha: 4af4260085204071f14689771609658fb52329e1
    landing_revision: null
    audit_ids:
    - audit-9193cb8ddfd6
    kind: result
    applied: true
    retired_at: '2026-08-11T12:37:31.504283+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1082
    audit_id: audit-9193cb8ddfd6
    attempt_id: attempt-b707ed02a354
    target_state: Done
    evidence_fingerprint: 9b2b997b620044ccd53da6072f11e1fdd456545a48d5d643f416f256730dc3dc
    status: In Validation
    audit_ids:
    - audit-9193cb8ddfd6
    kind: result
    applied: true
    created_at: '2026-08-11T12:37:31.504294+00:00'
    applied_at: '2026-08-11T12:37:38.897641+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-9193cb8ddfd6
    project_id: proj-14849f1b
    task_id: OOMPAH-1082
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9b2b997b620044ccd53da6072f11e1fdd456545a48d5d643f416f256730dc3dc
    attempts:
    - version: 1
      attempt_id: attempt-b707ed02a354
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9b2b997b620044ccd53da6072f11e1fdd456545a48d5d643f416f256730dc3dc
      created_at: '2026-08-11T12:34:07.866474+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T12:34:07.866474+00:00'
      branch_key: OOMPAH-1082
      selected_ref: 4af4260085204071f14689771609658fb52329e1
      selected_sha: 4af4260085204071f14689771609658fb52329e1
      verdict: pass
      completed_at: '2026-08-11T12:37:31.504054+00:00'
      ended_at: '2026-08-11T12:37:31.504054+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T12:30:38.817712+00:00'
    selected_ref: 4af4260085204071f14689771609658fb52329e1
    selected_sha: 4af4260085204071f14689771609658fb52329e1
    updated_at: '2026-08-11T12:37:31.504054+00:00'
  - version: 1
    audit_id: audit-a54c56f04b36
    project_id: proj-14849f1b
    task_id: OOMPAH-1082
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9b2b997b620044ccd53da6072f11e1fdd456545a48d5d643f416f256730dc3dc
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T12:30:38.817712+00:00'
    selected_ref: 4af4260085204071f14689771609658fb52329e1
    selected_sha: 4af4260085204071f14689771609658fb52329e1
    updated_at: '2026-08-11T12:37:31.504054+00:00'
    eligible_at: '2026-08-11T12:37:31.504054+00:00'
    prerequisite_audit_id: audit-9193cb8ddfd6
  attempt_history:
  - version: 1
    attempt_id: attempt-b707ed02a354
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9b2b997b620044ccd53da6072f11e1fdd456545a48d5d643f416f256730dc3dc
    created_at: '2026-08-11T12:34:07.866474+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T12:34:07.866474+00:00'
    branch_key: OOMPAH-1082
    selected_ref: 4af4260085204071f14689771609658fb52329e1
    selected_sha: 4af4260085204071f14689771609658fb52329e1
oompah.task_costs:
  total_input_tokens: 330
  total_output_tokens: 11039
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 330
      output_tokens: 11039
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 330
    output_tokens: 11039
    cost_usd: 0.0
    recorded_at: '2026-08-11T12:37:49.767884+00:00'
---
## Summary

Triggered by: OOMPAH-1072. Live evidence: Merged was requested and the coordinator correctly created a Done prerequisite audit plus Merged audit. Done audit-00d5d7755c13 passed at 10:43:03 and left In Validation as designed. The next Merged audit-078f5a8faba5 and durable workflow-job-ce9f7c40c06a44ebb780a1c28c811c9d remained pending/queued with attempts=0 across graceful restart until an 11:02 owner workaround, despite available audit capacity. Health also reported it stale using the chain creation time 08:56, including the period when Merged was not yet eligible because Done was running. Scope: atomically mark/wake the next chained terminal stage when its prerequisite result commits; ensure durable workflow scheduling immediately revisits that exact job after PASS and restart; define pending age from the stage eligible-at boundary rather than initial blocked-chain creation; preserve distinct-auditor policy, exact evidence/revision binding, lane budgets/fairness, idempotent recovery, pause semantics, and no concurrent sibling launch. Relevant code: TerminalTransitionCoordinator advanced_target/result commit, terminal audit workflow jobs, Orchestrator audit-lane continuation/candidate cursor, and terminal_audit_health. Tests/acceptance: Done PASS makes the existing Merged job eligible and dispatchable within one bounded continuation without waiting for a full poll; crash/restart between result commit and wake converges once; blocked next stages do not age as stale; truly eligible unattempted stages do; capacity/pause waits remain truthful; no duplicate launch or bypass of independent candidates; focused tests and protected CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 11:30
---
Make chained terminal-audit successor eligibility durable and restart-safe, wake the exact successor after prerequisite PASS, and age only eligible stages at a2d82ab7009cdba0bb325296d26d73568906a593; 496 focused and 915 adjacent tests plus terminal scan pass.
---
author: oompah
created: 2026-08-11 11:35
---
Branch quality gate passed for `a2d82ab7009cdba0bb325296d26d73568906a593` using `make test` in 176.2s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 11:36
---
Independent exact-head review BLOCKED a2d82ab7009cdba0bb325296d26d73568906a593: prerequisite_audit_id is persisted but not enforced. An eligible Merged stage referencing audit-done-other can fail open and dispatch using a different same-authority Done PASS audit-done-a; coordinator PASS stamping can also preserve the wrong ID while making it eligible. Author is fixing exact prerequisite identity enforcement plus wrong/missing/stale negative regressions; this head will not merge.
---
author: oompah
created: 2026-08-11 11:51
---
Review blocker corrected and pushed at exact rebased head ae1389772b9bbe7f8cb72cf3e882239bd54d85d3 on main 712309b8179036474e40c5fd26f7d2b3c2a4b9b0. Exact prerequisite audit identity is now enforced during Done→Merged stamping, dispatch, restart wake reconstruction, and direct Merged PASS result application; missing/stale/failed/cross-authority references fail closed, with a narrow documented prereq=None legacy migration. Combined OOMPAH-1080/OOMPAH-1082 suite: 799 passed; adjacent suite: 915 passed, 2 expected xfails; terminal mutation scan: 21/21. Fresh independent exact-head re-review and protected CI are running.
---
author: oompah
created: 2026-08-11 11:55
---
Fresh exact-head review BLOCKED ae1389772b9bbe7f8cb72cf3e882239bd54d85d3 on a recovery-chain deadlock: failed/exhausted Done -> owner rearm appends a new Done audit but leaves the pending Merged successor bound to the superseded failed prerequisite. The fresh Done PASS then cannot stamp/wake Merged, which remains pending forever with eligible_at=None. Author is adding atomic exact successor rebinding on rearm plus ambiguity/stale/cross-authority/restart regressions; this head will not merge.
---
author: oompah
created: 2026-08-11 12:08
---
Independent exact-head re-review ACCEPT for 4af4260085204071f14689771609658fb52329e1. Production reproducer confirms exhausted Done gen7 -> fresh owner rearm gen8 atomically rebinds the same Merged record while ineligible; restart replay coalesces; fresh Done PASS stamps and dispatches that exact Merged. Wrong fingerprint/workflow/ref/SHA/landing/generation/eligibility/attempt state fails closed with byte-identical metadata and no tracker write. Independent combined suite: 808 passed; terminal mutation scan 21/21; diff check clean.
---
author: oompah
created: 2026-08-11 12:17
---
Correct exact-head prerequisite chaining and owner-rearm recovery at 4af4260085204071f14689771609658fb52329e1; 808 combined tests, 915 adjacent tests, mutation scan, independent ACCEPT, and protected CI pass.
---
author: oompah
created: 2026-08-11 12:22
---
Branch quality gate passed for `4af4260085204071f14689771609658fb52329e1` using `make test` in 179.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 12:30
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 12:34
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 12:34
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 12:37
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- implementation.eligible_at_field: terminal_audit.py defines durable stage eligibility boundary
- implementation.prerequisite_audit_id_field: terminal_audit.py defines exact prerequisite binding
- implementation.successor_wake: terminal_transition_coordinator.py line 4943-4945 sets eligible_at=now and prerequisite_audit_id
- implementation.audit_lane_continuation: orchestrator.py line 11859-11860 triggers bounded continuation immediately
- implementation.aging_correct: terminal_audit_health.py line 72-76 uses eligible_at for pending age, returns None for blocked stages
- implementation.exact_prerequisite_enforcement: auditor_dispatch.py and terminal_transition_coordinator.py validate prerequisite_audit_id match
- implementation.owner_rearm_rebinding: terminal_transition_coordinator.py lines 2756-2780 atomically rebind successors
- implementation.restart_recovery: orchestrator.py lines 17629-17643 reconstruct and immediately revisit eligible stages
- test_coverage.done_merged_chain: test_pass_on_done_wakes_its_exact_merged_successor verifies wake mechanism
- test_coverage.chain_progression: test_pass_on_done_keeps_issue_in_validation_until_merged verifies blocking
- test_coverage.combined_tests: 808 passed
- test_coverage.adjacent_tests: 915 passed
- test_coverage.mutation_scan: 21/21 passed
- quality_gate.command: make test
- quality_gate.duration_seconds: 179.7
- quality_gate.status: passed
- quality_gate.review_status: independent exact-head ACCEPTED
---
author: oompah
created: 2026-08-11 12:37
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 87, Tool calls: 40
- Tokens: 330 in / 11.0K out [11.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 39s
- Log: OOMPAH-1082__20260811T123421Z.jsonl
---
<!-- COMMENTS:END -->
