---
id: OOMPAH-975
type: bug
status: Merged
priority: 1
title: Carry trusted composed landing heads into rollup terminal transitions
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T21:14:31.760374Z'
updated_at: '2026-08-09T23:03:59.052475Z'
work_branch: OOMPAH-975
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/782
review_number: '782'
review_head: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-975
  head_sha: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
  submitted_at: '2026-08-09T21:45:55.062482+00:00'
  updated_at: '2026-08-09T21:45:55.062482+00:00'
oompah.work_branch: OOMPAH-975
oompah.review_url: https://github.com/lesserevil/oompah/pull/782
oompah.review_number: '782'
oompah.target_branch: main
oompah.review_head: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-8f62ad9b36f0
    project_id: proj-14849f1b
    task_id: OOMPAH-975
    digest: 359fd89c7c4eb5ac1aec11ed4c75a771a703477e08b7702059d2e1eea95a9fbf
  - version: 1
    audit_id: audit-b8647366926c
    project_id: proj-14849f1b
    task_id: OOMPAH-975
    digest: 359fd89c7c4eb5ac1aec11ed4c75a771a703477e08b7702059d2e1eea95a9fbf
  oompah.terminal_override_records:
  - version: 1
    override_id: override-7420e162bf78
    project_id: proj-14849f1b
    task_id: OOMPAH-975
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 359fd89c7c4eb5ac1aec11ed4c75a771a703477e08b7702059d2e1eea95a9fbf
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Exact implementation head d173e88eec2552ee639ef235a772fceeed8b66e6 passed
      protected Python 3.11/3.12/3.13 and independent 553-test review, merged via
      PR #782 as e8be4d38d15f13859acb13865102bdbd86a8ec23, and is deployed in exact
      running main 25154c8b709f5916d5a9744d2b2fe9979d64799f. The terminal auditor''s
      duplicate full suite stalled in jbd2 after protected evidence was already green
      and its shell mutation is policy-incompatible.'
    created_at: '2026-08-09T23:03:54.471449+00:00'
    selected_ref: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
    selected_sha: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-8f62ad9b36f0
    project_id: proj-14849f1b
    task_id: OOMPAH-975
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 359fd89c7c4eb5ac1aec11ed4c75a771a703477e08b7702059d2e1eea95a9fbf
    attempts:
    - version: 1
      attempt_id: attempt-b69cff5382a7
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 359fd89c7c4eb5ac1aec11ed4c75a771a703477e08b7702059d2e1eea95a9fbf
      created_at: '2026-08-09T22:29:15.942758+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T22:29:15.942758+00:00'
      branch_key: OOMPAH-975
      selected_ref: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
      selected_sha: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
      failure_classification: infrastructure_error
      origin: coordinator_abandoned_recovery
      ended_at: '2026-08-09T23:01:24.040479+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-489a1f3fae11
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 359fd89c7c4eb5ac1aec11ed4c75a771a703477e08b7702059d2e1eea95a9fbf
      created_at: '2026-08-09T23:01:27.298881+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T23:01:27.298881+00:00'
      branch_key: OOMPAH-975
      selected_ref: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
      selected_sha: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
      candidate_rotation_count: 1
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-09T22:26:07.264673+00:00'
    selected_ref: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
    selected_sha: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
    updated_at: '2026-08-09T23:01:27.298881+00:00'
  - version: 1
    audit_id: audit-b8647366926c
    project_id: proj-14849f1b
    task_id: OOMPAH-975
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 359fd89c7c4eb5ac1aec11ed4c75a771a703477e08b7702059d2e1eea95a9fbf
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-09T22:26:07.264673+00:00'
    selected_ref: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
    selected_sha: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
  attempt_history:
  - version: 1
    attempt_id: attempt-b69cff5382a7
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 359fd89c7c4eb5ac1aec11ed4c75a771a703477e08b7702059d2e1eea95a9fbf
    created_at: '2026-08-09T22:29:15.942758+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T22:29:15.942758+00:00'
    branch_key: OOMPAH-975
    selected_ref: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
    selected_sha: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
    failure_classification: infrastructure_error
    origin: coordinator_abandoned_recovery
    ended_at: '2026-08-09T23:01:24.040479+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-489a1f3fae11
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 359fd89c7c4eb5ac1aec11ed4c75a771a703477e08b7702059d2e1eea95a9fbf
    created_at: '2026-08-09T23:01:27.298881+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T23:01:27.298881+00:00'
    branch_key: OOMPAH-975
    selected_ref: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
    selected_sha: 0cbca98c1d6f6b3490a93b4164ef370ac01db432
    candidate_rotation_count: 1
---
## Summary

Triggered by: OOMPAH-940

Live all-enforce rollout regression found after OOMPAH-940 child delivery on 2026-08-09. Done children OOMPAH-787, OOMPAH-794, OOMPAH-797, and OOMPAH-798 have canonical durable landing facts (landing_source=<task>, landing_target=epic-OOMPAH-767/771, landing_revision=33f85955b3c1285987253c2ff17b31f574c6d12f), but no standalone work_branch/task_head because their owner-completed commits were composed into the epic. The workflow decision correctly emits terminal.immediate_target_landing_proven and parent_rollup_review requesting Merged, yet the handler builds TransitionIntent.exact_head=null; TaskTransitionService rejects transition.head_required and the jobs exhaust as current policy failures. Implementation scope: thread the canonical trusted landing revision through parent_rollup_review revalidation/effect/transition intent whenever immediate-target landing is proven; require the landing source/target and task evidence generation to remain current; supersede/retry historical exhausted null-head jobs after the fixed decision generation; preserve exact-head fail-closed behavior when landing proof is absent, stale, wrong-source, wrong-target, or mutable. Relevant code: universal workflow facts/decisions, epic parent rollup review handler, transition-intent construction, durable job recovery/current exhaustion. Required tests: composed Done child with no task branch but exact durable epic landing reaches Merged; all four live shapes; stale/mismatched/no landing remains head_required without exhausting an administratively recoverable job; restart/replay is idempotent; independent standalone tasks still require their exact accepted head. Acceptance: these four historical jobs are naturally superseded or retired, current exhausted returns to zero, no broad status/database edits are used, focused workflow/transition/restart suites and full gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 21:17
---
The live affected set expanded deterministically from four to six as the generation-852 queue drained: OOMPAH-889 and OOMPAH-894 have the same terminal.immediate_target_landing_proven shape, exact landing revision 33f85955b3c1285987253c2ff17b31f574c6d12f into epic-OOMPAH-763, empty task branch/head, and null-head transition rejection. They were also retained through terminal-provenance authority; implementation remains terminal. Regression coverage and natural supersession must include all six rows.
---
author: oompah
created: 2026-08-09 21:22
---
Implementation started in isolated worktree /home/shedwards/src/oompah-975 on branch OOMPAH-975 at base 312c18ae3. Confirmed six current exhausted parent_rollup_review jobs (OOMPAH-787, -794, -797, -798, -889, -894) all lose trusted composed landing revision 33f85955... before TransitionIntent. Fix will fence source/target/evidence at revalidation, carry the exact landing SHA through transition and terminal-audit binding, preserve standalone exact-head requirements, and cover natural current-exhaustion retirement/restart replay.
---
author: oompah
created: 2026-08-09 21:42
---
Implementation complete on branch OOMPAH-975. The parent-rollup authority now carries a canonical exact composed landing SHA through revalidation, effect receipt, verification, transition intent, and terminal-audit binding; source/target/project/revision/durability remain fail-closed at the final mutation guard. Regression coverage includes all six live shapes (OOMPAH-787/-794/-797/-798/-889/-894), absent/stale/wrong/mutable landing rejection, actual TaskTransitionService staging, restart journal replay, audit coalescing, standalone no-head rejection, and owner-driven exhaustion retirement without automatic rearm. Focused workflow/transition/runtime gate: 630 passed; terminal mutation scan passed. Preparing exact-head commit/push for the configured full branch gate.
---
author: oompah
created: 2026-08-09 21:43
---
Committed and pushed 2fd04d272 on OOMPAH-975. Trusted composed parent landing heads now remain exact through rollup revalidation/effect/verification/transition and bind the terminal audit; all authority fields are rechecked at final mutation. Added six-shape, fail-closed, actual transition, restart/replay, coalescing, runtime-guard, and standalone-head regressions. Focused relevant suites: 630 passed; task mutation scan passed. Existing owner-projection retirement remains responsible for superseding old exhausted generations without unsafe rearm.
---
author: oompah
created: 2026-08-09 21:45
---
Fresh post-implementation scan expanded the live same-shape corpus by 14 current exhausted Done children under OOMPAH-763: OOMPAH-910, -911, -914, -915, -916, -917, -918, -919, -920, -921, -926, -929, -930, and -931. Each has exact durable parent-scoped landing authority and the same historical null-head parent_rollup_review rejection. Supported terminal-provenance retain was applied externally to preserve owner authority; this change does not rearm or edit rows. Regression parameterization now names all 20 observed production shapes; the generic implementation path is identical across them.
---
author: oompah
created: 2026-08-09 21:47
---
Updated exact head 0cbca98c1 expands the regression matrix to all 20 live composed Done child shapes, including newly observed OOMPAH-910/-911/-914 through -921/-926/-929 through -931 under OOMPAH-763. Relevant workflow/transition/runtime suites now pass 644 tests; terminal mutation scan passed. No exhausted row rearm or database edit is introduced; fresh owner scans retire/supersede historical generations.
---
author: oompah
created: 2026-08-09 21:50
---
Branch quality gate passed for `0cbca98c1d6f6b3490a93b4164ef370ac01db432` using `make test` in 171.9s. Review creation may proceed.
---
author: oompah
created: 2026-08-09 21:50
---
Resubmit updated exact head 0cbca98c1 after expanding the live corpus regression matrix to all 20 observed shapes; 644 focused tests pass.
---
author: oompah
created: 2026-08-09 21:53
---
Security/replay review hardening pushed at ad70402ee. Supplied terminal-audit revision authority is now restricted to a mutation-guarded integrator request for a parented, headless, current-Done child targeting Merged; the exact SHA/ref/project must resolve identically in the managed repo. Wrong role/status/target/project, parentless/ordinary-head, missing guard, non-SHA ref, unavailable SHA, and resolution mismatch all reject before mutation. The transition-service exception separately requires observed Done, and native blank project IDs are normalized before the final authority CAS. Relevant five-file suite: 655 passed; independent affected-suite review: 548 passed, no remaining blocker.
---
author: oompah
created: 2026-08-09 22:06
---
Rebased after OOMPAH-974 merged/deployed. Exact combined head d173e88eec2552ee639ef235a772fceeed8b66e6 contains main merge 9ea2d4d07 plus the reviewed OOMPAH-975 patch. Combined affected suite: 953 passed in 25.18 seconds; terminal status mutation scan passed 20/20; diff check clean. PR #782 protected Python 3.11/3.12/3.13 checks are rerunning on this exact composition.
---
author: oompah
created: 2026-08-09 22:26
---
Protected rerun is green: exact branch head d173e88eec2552ee639ef235a772fceeed8b66e6 passed Python 3.11/3.12/3.13 and PR #782 auto-merged to main as e8be4d38d15f13859acb13865102bdbd86a8ec23. The merged local/remote task branches and worktree were pruned. Deployment is intentionally batched with the active OOMPAH-974/OOMPAH-976 fixes to avoid an extra restart on the currently known-starving runtime.
---
author: oompah
created: 2026-08-09 22:26
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 22:29
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 22:29
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 23:01
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 23:01
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
