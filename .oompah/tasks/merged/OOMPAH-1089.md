---
id: OOMPAH-1089
type: bug
status: Merged
priority: 1
title: Regenerate current review jobs after stale-evidence exhaustion
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T14:22:55.237924Z'
updated_at: '2026-08-11T17:29:13.477374Z'
work_branch: OOMPAH-1089
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/824
review_number: '824'
review_head: ae985020931e3c17f1e904921b34f65207bd85af
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: review-stale-evidence-regeneration-20260811
  request_fingerprint: 632471a88f61cd821faefecc9c5fba392deb4e027a77c57f2d54abfef736019d
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1089
  head_sha: ae985020931e3c17f1e904921b34f65207bd85af
  submitted_at: '2026-08-11T15:14:03.387343+00:00'
  updated_at: '2026-08-11T15:14:03.387343+00:00'
oompah.work_branch: OOMPAH-1089
oompah.review_url: https://github.com/lesserevil/oompah/pull/824
oompah.review_number: '824'
oompah.target_branch: main
oompah.review_head: ae985020931e3c17f1e904921b34f65207bd85af
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-22603e70f558
    project_id: proj-14849f1b
    task_id: OOMPAH-1089
    digest: 0c6a9b4e3b82298ec68113d40ce0c1335e5e7b05c1d4cec01bf5c52bb99e7472
  - version: 1
    audit_id: audit-a1299b687c8f
    project_id: proj-14849f1b
    task_id: OOMPAH-1089
    digest: 0c6a9b4e3b82298ec68113d40ce0c1335e5e7b05c1d4cec01bf5c52bb99e7472
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1089","audit-22603e70f558","attempt-832db0c7fd32"]': '2026-08-11T15:53:44.665717+00:00'
    '["proj-14849f1b","OOMPAH-1089","audit-a1299b687c8f","attempt-8e62cd45a8f7"]': '2026-08-11T17:29:00.575171+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1089
    target_state: Done
    evidence_fingerprint: 0c6a9b4e3b82298ec68113d40ce0c1335e5e7b05c1d4cec01bf5c52bb99e7472
    workflow_revision: null
    selected_ref: ae985020931e3c17f1e904921b34f65207bd85af
    selected_sha: ae985020931e3c17f1e904921b34f65207bd85af
    landing_revision: null
    audit_ids:
    - audit-22603e70f558
    kind: result
    applied: true
    retired_at: '2026-08-11T15:53:44.665733+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1089
    target_state: Merged
    evidence_fingerprint: 0c6a9b4e3b82298ec68113d40ce0c1335e5e7b05c1d4cec01bf5c52bb99e7472
    workflow_revision: null
    selected_ref: ae985020931e3c17f1e904921b34f65207bd85af
    selected_sha: ae985020931e3c17f1e904921b34f65207bd85af
    landing_revision: null
    audit_ids:
    - audit-a1299b687c8f
    kind: result
    applied: true
    retired_at: '2026-08-11T17:29:00.575192+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1089
    audit_id: audit-22603e70f558
    attempt_id: attempt-832db0c7fd32
    target_state: Done
    evidence_fingerprint: 0c6a9b4e3b82298ec68113d40ce0c1335e5e7b05c1d4cec01bf5c52bb99e7472
    status: In Validation
    audit_ids:
    - audit-22603e70f558
    kind: result
    applied: true
    created_at: '2026-08-11T15:53:44.665744+00:00'
    applied_at: '2026-08-11T15:53:53.044888+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1089
    audit_id: audit-a1299b687c8f
    attempt_id: attempt-8e62cd45a8f7
    target_state: Merged
    evidence_fingerprint: 0c6a9b4e3b82298ec68113d40ce0c1335e5e7b05c1d4cec01bf5c52bb99e7472
    status: Merged
    audit_ids:
    - audit-a1299b687c8f
    kind: result
    applied: true
    created_at: '2026-08-11T17:29:00.575206+00:00'
    applied_at: '2026-08-11T17:29:11.730290+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-22603e70f558
    project_id: proj-14849f1b
    task_id: OOMPAH-1089
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0c6a9b4e3b82298ec68113d40ce0c1335e5e7b05c1d4cec01bf5c52bb99e7472
    attempts:
    - version: 1
      attempt_id: attempt-832db0c7fd32
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0c6a9b4e3b82298ec68113d40ce0c1335e5e7b05c1d4cec01bf5c52bb99e7472
      created_at: '2026-08-11T15:50:24.200750+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T15:50:24.200750+00:00'
      branch_key: OOMPAH-1089
      selected_ref: ae985020931e3c17f1e904921b34f65207bd85af
      selected_sha: ae985020931e3c17f1e904921b34f65207bd85af
      verdict: pass
      completed_at: '2026-08-11T15:53:44.665524+00:00'
      ended_at: '2026-08-11T15:53:44.665524+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T15:35:15.992180+00:00'
    eligible_at: '2026-08-11T15:35:15.992180+00:00'
    selected_ref: ae985020931e3c17f1e904921b34f65207bd85af
    selected_sha: ae985020931e3c17f1e904921b34f65207bd85af
    updated_at: '2026-08-11T15:53:44.665524+00:00'
  - version: 1
    audit_id: audit-a1299b687c8f
    project_id: proj-14849f1b
    task_id: OOMPAH-1089
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0c6a9b4e3b82298ec68113d40ce0c1335e5e7b05c1d4cec01bf5c52bb99e7472
    attempts:
    - version: 1
      attempt_id: attempt-8e62cd45a8f7
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0c6a9b4e3b82298ec68113d40ce0c1335e5e7b05c1d4cec01bf5c52bb99e7472
      created_at: '2026-08-11T17:20:32.729191+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T17:20:32.729191+00:00'
      branch_key: OOMPAH-1089
      selected_ref: ae985020931e3c17f1e904921b34f65207bd85af
      selected_sha: ae985020931e3c17f1e904921b34f65207bd85af
      verdict: pass
      completed_at: '2026-08-11T17:29:00.574985+00:00'
      ended_at: '2026-08-11T17:29:00.574985+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T15:35:15.992180+00:00'
    prerequisite_audit_id: audit-22603e70f558
    selected_ref: ae985020931e3c17f1e904921b34f65207bd85af
    selected_sha: ae985020931e3c17f1e904921b34f65207bd85af
    updated_at: '2026-08-11T17:29:00.574985+00:00'
    eligible_at: '2026-08-11T15:53:44.665524+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-832db0c7fd32
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0c6a9b4e3b82298ec68113d40ce0c1335e5e7b05c1d4cec01bf5c52bb99e7472
    created_at: '2026-08-11T15:50:24.200750+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T15:50:24.200750+00:00'
    branch_key: OOMPAH-1089
    selected_ref: ae985020931e3c17f1e904921b34f65207bd85af
    selected_sha: ae985020931e3c17f1e904921b34f65207bd85af
  - version: 1
    attempt_id: attempt-8e62cd45a8f7
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0c6a9b4e3b82298ec68113d40ce0c1335e5e7b05c1d4cec01bf5c52bb99e7472
    created_at: '2026-08-11T17:20:32.729191+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T17:20:32.729191+00:00'
    branch_key: OOMPAH-1089
    selected_ref: ae985020931e3c17f1e904921b34f65207bd85af
    selected_sha: ae985020931e3c17f1e904921b34f65207bd85af
oompah.task_costs:
  total_input_tokens: 282
  total_output_tokens: 9247
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 282
      output_tokens: 9247
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 282
    output_tokens: 9247
    cost_usd: 0.0
    recorded_at: '2026-08-11T15:54:03.900372+00:00'
---
## Summary

Triggered by: OOMPAH-1086

Live incident: after deploying exact review-generation synchronization on 2026-08-11, OOMPAH-1086 had open PR 823 at exact head 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f, a current-main merge candidate, all protected Python 3.11/3.12/3.13 checks green, an accepted exact-head independent review, and work decision review.ready_to_merge. The durable review_merge effect then exhausted on its first attempt with stale_evidence: review, repository, branch, or exact head identity changed. The next projection became critical retry.exhausted with no durable job, even though this identity/base evolution is a normal optimistic-concurrency race that should generate fresh exact authority. OOMPAH-1087 showed the same terminal retry projection after its base generation changed. Scope: classify review identity, head, repository, branch, and target-base changes observed between intent, revalidation, effect, and observation as superseded generation when a current valid open review can be re-observed; enqueue exactly one fresh review monitor, gate, or merge job for the new evidence; preserve fail-closed behavior and bounded retries for genuinely unavailable, malformed, forked, conflicting, or policy-invalid reviews; and ensure retry budgets are generation-scoped rather than poisoning a newer evidence generation. Required tests: identity enrichment after deployment, base-only advance, head advance, synchronize during merge intent, restart between stale detection and regeneration, and repeated webhook/poll races must all supersede stale authority and converge to one current job; stale authority must never merge; missing review, wrong repo/base/source, conflicts, and persistent provider errors must remain actionable after bounded attempts. Acceptance: normal review evidence changes cannot strand an otherwise valid In Review task in retry.exhausted, current exact authority is regenerated automatically, focused review/workflow/liveness tests and terminal mutation scan pass, and protected CI is green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 14:23
---
Direct owner claimed from the live OOMPAH-1086 and OOMPAH-1087 evidence. OOMPAH-1086 review_merge job workflow-job-6f277655ecc4449db3147f82222169b0 exhausted at effect_pending on its first stale-evidence observation despite PR 823 being open, exact-head green, current-main mergeable, and independently accepted. Repair is starting from deployed main 6a0f7210 with generation-scoped stale-evidence regeneration tests.
---
author: oompah
created: 2026-08-11 14:42
---
Live evidence confirmed both OOMPAH-1086 and OOMPAH-1087 review_merge jobs exhausted at effect_pending after one stale_evidence refusal. OOMPAH-1086's accepted integration record lacked base_branch/base_sha while the fresh PR 823 observation supplied a complete exact same-repository identity, so selection reached merge but the strict effect correctly refused it. Repair now routes missing accepted base identity through exact head/base reconciliation, supersedes an old merge effect when the second observation or forge CAS proves a valid newer review generation, and rearms stale exhaustion only for a complete non-forked non-conflicting current review identity. Wrong repositories/source/base, conflicts, missing reviews, and provider errors stay fail-closed. Green so far: 387 review/runtime/liveness tests, 74 architecture/churn tests, terminal mutation scan 21/21, production Ruff and py_compile.
---
author: oompah
created: 2026-08-11 14:44
---
Implementation candidate pushed at exact head e8c8d052c3d28b0eb764f8d1b293227c7f10f72e. The repair enriches missing accepted base identity through exact review_head_reconciliation; turns synchronize/base/CAS changes seen after revalidation into durable supersession instead of stale_evidence exhaustion; and lets a published complete same-repository successor generation retire only prior stale-review exhaustion. Exact identity checks remain required for review ID, task/source/target branches, repository equality, accepted standalone authority, and 40/64-hex head/base. Invalid fork/source/target/base, conflict, missing-review, and provider-error cases remain bounded/actionable with zero forge merge writes. Evidence: 393 review/workflow/runtime/liveness tests green, 74 architecture/churn tests green, mutation scan 21/21, production Ruff/py_compile, diff check, paranoid secrets, and commit hooks. Awaiting independent exact-head review; not submitted or merged.
---
author: oompah
created: 2026-08-11 14:48
---
Rebased the reviewed implementation onto current origin/main fe9599111d478b8221a2949c878fecb61d558760 and pushed replacement exact head a6ae095fda9b07d3a113e44c74591387e73f6053. Post-rebase verification: 391 focused workflow/review/liveness tests passed; terminal-audit mutation scan 21/21; git diff --check clean. Awaiting fresh independent exact-head review before submission.
---
author: oompah
created: 2026-08-11 14:59
---
Independent review found and repaired a TOCTOU in successor-generation retry authority. Successor eligibility and ordinary exhaustion handling previously performed separate current-exhaustion reads, so a concurrent replacement exhaustion could be evaluated under stale predecessor proof. Both decisions now consume one immutable tuple of frozen WorkflowJob rows, with a deterministic substitution regression proving only one authority read occurs and a later current-generation exhaustion cannot inherit the older proof. Replacement candidate pushed at exact head 6393f0b490c7b91b6783557fc2f44a08127f0fa7 (force-with-lease against a6ae095fda9b07d3a113e44c74591387e73f6053). Evidence: 392 focused review/work-decision/controller/runtime/liveness tests passed; terminal-audit mutation scan 21/21; git diff --check and py_compile clean; commit hooks and paranoid secret scans passed. Not submitted or merged; requires fresh independent exact-head review.
---
author: oompah
created: 2026-08-11 15:14
---
Rebased the independently ACCEPTED repair onto current origin/main 6449341d762d9c7645271b8479dfa406e648be54 and pushed replacement exact head ae985020931e3c17f1e904921b34f65207bd85af. git range-diff proves both commits patch-equivalent to the accepted 6393f0b490c7b91b6783557fc2f44a08127f0fa7 series; post-rebase 392 focused review/controller/runtime/liveness tests passed, terminal mutation scan 21/21, and diff check is clean. The accepted review verified the exhaustion TOCTOU is closed by one immutable row tuple and all exact identity/fail-closed paths remain bounded. Ready for canonical validation.
---
author: oompah
created: 2026-08-11 15:14
---
Regenerate fresh exact review generations after stale-evidence exhaustion and bind successor proof to one immutable exhaustion snapshot.
---
author: oompah
created: 2026-08-11 15:20
---
Branch quality gate passed for `ae985020931e3c17f1e904921b34f65207bd85af` using `make test` in 181.0s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 15:35
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 15:50
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 15:50
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 15:53
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- test_coverage.identity_enrichment: test_legacy_review_identity_is_enriched_before_merge
- test_coverage.base_advance: test_base_only_change_requeues_exact_generation_for_regating, test_base_only_reconciliation_resumes_after_metadata_checkpoint
- test_coverage.head_advance: test_head_change_supersedes_queued_merge_without_forge_write
- test_coverage.merge_synchronize: test_synchronize_between_merge_revalidation_and_effect_blocks_merge
- test_coverage.restart_scenarios: test_head_reconciliation_resumes_after_metadata_checkpoint_restart, test_review_successor_regeneration_survives_restart_and_coalesces
- test_coverage.webhook_poll_races: test_review_successor_regeneration_survives_restart_and_coalesces
- test_coverage.fail_closed_invalid: test_invalid_merge_races_exhaust_without_forge_write (fork, source, target, conflict, missing), test_head_reconciliation_fails_closed_on_identity_drift
- quality_gate: make test passed 181 seconds on exact head ae985020931e3c17f1e904921b34f65207bd85af
- verification: 392 focused tests, mutation scan 21/21, diff check clean, production Ruff/py_compile, independently ACCEPTED exact-head review, rebased with patch equivalence proven
- acceptance_criteria[0]: Normal review evidence changes cannot strand In Review tasks in retry.exhausted
- acceptance_criteria[1]: Current exact authority is regenerated automatically
- acceptance_criteria[2]: Focused review/workflow/liveness tests passing
- acceptance_criteria[3]: Terminal mutation scan passing
- acceptance_criteria[4]: Protected CI green
---
author: oompah
created: 2026-08-11 15:54
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 75, Tool calls: 34
- Tokens: 282 in / 9.2K out [9.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 36s
- Log: OOMPAH-1089__20260811T155053Z.jsonl
---
author: oompah
created: 2026-08-11 17:20
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 17:20
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 17:29
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- implementation[0]: _head_reconciliation_identity validates head/base changes
- implementation[1]: _successor_generation detects evidence changes
- implementation[2]: _review_successor_generation_proven validates successor eligibility
- implementation[3]: terminal_transition_coordinator binds successor authority
- implementation[4]: fail_closed for malformed/forked/conflicting reviews
- tests[0]: test_legacy_review_identity_is_enriched_before_merge
- tests[1]: test_base_only_change_requeues_exact_generation_for_regating
- tests[2]: test_base_only_reconciliation_resumes_after_metadata_checkpoint
- tests[3]: test_head_change_supersedes_queued_merge_without_forge_write
- tests[4]: test_synchronize_between_merge_revalidation_and_effect_blocks_merge
- tests[5]: test_head_reconciliation_resumes_after_metadata_checkpoint_restart
- tests[6]: test_review_successor_regeneration_survives_restart_and_coalesces
- tests[7]: test_invalid_merge_races_exhaust_without_forge_write
- tests[8]: test_head_reconciliation_fails_closed_on_identity_drift
- quality_gate: make test passed at ae985020931e3c17f1e904921b34f65207bd85af (180.97 seconds)
- acceptance_criteria[0]: Normal review evidence changes cannot strand In Review tasks
- acceptance_criteria[1]: Current exact authority regenerated automatically
- acceptance_criteria[2]: Focused review/workflow/liveness tests passing
- acceptance_criteria[3]: Terminal mutation scan 21/21
- acceptance_criteria[4]: Protected CI green
---
<!-- COMMENTS:END -->
