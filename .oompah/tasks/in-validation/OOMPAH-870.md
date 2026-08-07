---
id: OOMPAH-870
type: bug
status: In Validation
priority: 1
title: Land already-contained Ready heads without requiring a zero-diff forge review
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T05:24:09.733359Z'
updated_at: '2026-08-07T08:41:50.349812Z'
work_branch: OOMPAH-870
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/736
review_number: '736'
review_head: aaaebbfa5152e9942a1decd9ef2d319573ca0493
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b4c55ab50f13d1fbeeb1bf36f04eba9e9b39b2039e5f815d1f54b3740bb679c6
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-07T07:16:55.334174+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed the supplied peer corpus. The closest tasks\
    \ (OOMPAH-208, OOMPAH-162, and OOMPAH-165) are terminal and address different\
    \ landing/reconciliation behavior; no active duplicate is confirmed.\nFocus handoff:\
    \ duplicate_detector  \nDuplicate preflight verdict: no_duplicate  \nMatches:\
    \ none\n\nEvidence: Reviewed the supplied peer corpus. The closest tasks (OOMPAH-208,\
    \ OOMPAH-162, and OOMPAH-165) are terminal and address different landing/reconciliation\
    \ behavior; no active duplicate is confirmed."
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
oompah.task_costs:
  total_input_tokens: 46606
  total_output_tokens: 279
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46512
      output_tokens: 258
      cost_usd: 0.0
    unknown:
      input_tokens: 94
      output_tokens: 21
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46512
    output_tokens: 258
    cost_usd: 0.0
    recorded_at: '2026-08-07T07:16:55.317918+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 94
    output_tokens: 21
    cost_usd: 0.0
    recorded_at: '2026-08-07T08:41:37.119405+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-870__20260807T071504Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-870
    source_sha: 45e2b83356dd041200d7cad0970c7e6f939dc757
    completed_at: '2026-08-07T07:16:55.339801+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-870
  head_sha: aaaebbfa5152e9942a1decd9ef2d319573ca0493
  submitted_at: '2026-08-07T07:58:47.339172+00:00'
  updated_at: '2026-08-07T07:58:47.339172+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/736
oompah.review_number: '736'
oompah.work_branch: OOMPAH-870
oompah.target_branch: main
oompah.review_head: aaaebbfa5152e9942a1decd9ef2d319573ca0493
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-78d38e3cdbe2
    project_id: proj-14849f1b
    task_id: OOMPAH-870
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 168de75892a9c5f43182a985946be64d63a0498e28e3f581de94db2897f452c7
    attempts:
    - version: 1
      attempt_id: attempt-7d919149aed7
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 168de75892a9c5f43182a985946be64d63a0498e28e3f581de94db2897f452c7
      created_at: '2026-08-07T08:35:29.718500+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-07T08:35:29.718500+00:00'
      branch_key: OOMPAH-870
      selected_ref: aaaebbfa5152e9942a1decd9ef2d319573ca0493
      selected_sha: aaaebbfa5152e9942a1decd9ef2d319573ca0493
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-07T08:21:30.064281+00:00'
    selected_ref: aaaebbfa5152e9942a1decd9ef2d319573ca0493
    selected_sha: aaaebbfa5152e9942a1decd9ef2d319573ca0493
    updated_at: '2026-08-07T08:35:29.718500+00:00'
  - version: 1
    audit_id: audit-ad075da8086f
    project_id: proj-14849f1b
    task_id: OOMPAH-870
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 168de75892a9c5f43182a985946be64d63a0498e28e3f581de94db2897f452c7
    attempts: []
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-07T08:21:30.064281+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-7d919149aed7
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 168de75892a9c5f43182a985946be64d63a0498e28e3f581de94db2897f452c7
    created_at: '2026-08-07T08:35:29.718500+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-07T08:35:29.718500+00:00'
    branch_key: OOMPAH-870
    selected_ref: aaaebbfa5152e9942a1decd9ef2d319573ca0493
    selected_sha: aaaebbfa5152e9942a1decd9ef2d319573ca0493
---
## Summary

Triggered by: OOMPAH-612

Reproduce OOMPAH-612 after its exact accepted-head gate passes when the accepted branch head is already an ancestor of the target branch. The Ready integration path currently asks the forge for a replacement review even though the accepted head has zero target diff, receives no review, emits a persistent warning, and cannot reach a terminal state. Implement a durable Ready fast-path that revalidates exact accepted-head containment and terminal authority, records canonical no-op landing evidence, and advances through terminal audit/landing without creating or reusing an invalid review. Preserve OOMPAH-819 stale-review generation fences and OOMPAH-698 legacy In Review reconciliation semantics. Relevant code: integration/review staging, accepted-head containment checks, terminal transition coordinator, alert publication. Required tests: exact gate plus already-contained head terminates; stale or mismatched accepted heads remain rejected; restart/replay is idempotent; no forge warning is emitted for a valid zero-diff landing. Acceptance: an exact-gated Ready task whose accepted head is contained in target cannot deadlock waiting for an impossible forge review.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 07:14
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 07:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 07:16
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.5K in / 258 out [46.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 45s
- Log: OOMPAH-870__20260807T071504Z.jsonl
---
author: oompah
created: 2026-08-07 07:25
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-07 07:25
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 07:25
---
Understanding: The Ready integration path needs a durable zero-diff fast-path after the exact accepted-head gate. I will trace review staging, containment validation, terminal audit/landing, and alert publication; add regression tests for valid containment, stale/mismatched heads, idempotent replay, and no forge warning; then run focused checks.
---
author: oompah
created: 2026-08-07 07:28
---
Discovery: The affected path is Orchestrator._reconcile_standalone_ready_to_integrate_tasks in oompah/orchestrator.py. It validates the submitted branch/head and runs the exact quality gate, but when no live review remains it unconditionally reserves capacity and calls create_review; a valid accepted head already contained by the target therefore gets a forge no-review retry warning. Existing merged/Done reconciliation has containment helpers, but this Ready path lacks an accepted-generation containment CAS and durable terminal handoff. I am tracing coordinator and metadata contracts to preserve stale-generation fences and legacy In Review behavior.
---
author: oompah
created: 2026-08-07 07:46
---
Implementation: Added an exact accepted-head containment check with target-ref refresh and immutable merge-base validation, plus a durable IntegrationRecord(state=integrated) no-op landing marker. Valid contained Ready submissions enter the existing terminal transition coordinator without review creation; replay detects the marker before forge lookup. Unknown containment keeps the ordinary review path available, and stale authority is rechecked before and after evidence persistence.
---
author: oompah
created: 2026-08-07 07:51
---
Verification: The focused standalone reconciliation suite passes 64 tests, including exact-gated contained heads, canonical no-op replay, uncontained heads, and immutable SHA/target-ref containment. Directly affected terminal audit/fingerprint suites pass 183 tests. Python compilation and git diff checks pass. The repository's native  wrapper could not initialize because its validation lock path is read-only, so tests used the existing project test virtualenv directly; no test failure was observed.
---
author: oompah
created: 2026-08-07 07:54
---
Verification update: After adding the review-capacity bypass for proven zero-diff landings, the focused standalone suite remains green at 64 passed. The terminal audit/fingerprint neighbors remain green at 183 passed; compile and diff checks are clean.
---
author: oompah
created: 2026-08-07 07:56
---
Verification complete: Combined focused coverage passes 248 tests (65 standalone Ready reconciliation tests plus 183 terminal audit/fingerprint/coordinator tests). This includes a real coordinator test proving a contained head persists integrated evidence and stages the Done/Merged audit chain, as well as the review-capacity bypass, replay idempotence, stale/uncontained, and exact SHA containment cases.
---
author: oompah
created: 2026-08-07 07:58
---
Completion: Delivered and pushed commit aaaebbfa5152e9942a1decd9ef2d319573ca0493. Ready reconciliation now gates and revalidates the exact accepted SHA, bypasses review capacity for confirmed zero-diff landings, persists integrated no-op evidence, and enters the terminal audit coordinator without forge review creation. Focused verification is green at 248 tests; branch status is clean and up to date with origin.
---
author: oompah
created: 2026-08-07 07:59
---
Land already-contained Ready heads through durable no-op terminal audit without creating a forge review
---
author: oompah
created: 2026-08-07 07:59
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 191
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 33m 57s
- Log: OOMPAH-870__20260807T072531Z.jsonl
---
author: oompah
created: 2026-08-07 08:10
---
Branch quality gate passed for `aaaebbfa5152e9942a1decd9ef2d319573ca0493` using `make test` in 647.5s. Review creation may proceed.
---
author: oompah
created: 2026-08-07 08:21
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-07 08:21
---
YOLO: merged PR #736.
---
author: oompah
created: 2026-08-07 08:35
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-07 08:35
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-07 08:41
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 5
- Tokens: 94 in / 21 out [115 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 57s
- Log: OOMPAH-870__20260807T083555Z.jsonl
---
<!-- COMMENTS:END -->
