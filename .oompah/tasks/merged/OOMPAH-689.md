---
id: OOMPAH-689
type: task
status: Merged
priority: null
title: Do not poison successful handoff after expected non-running peer reads
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T00:13:22.222984Z'
updated_at: '2026-08-02T01:03:34.166908Z'
work_branch: OOMPAH-689
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/648
review_number: '648'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 66d5b7ce2f2319aa8dcd315591a6a4c8a6b74afbb7407da660c6eda8b548ac73
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-02T00:15:10.974843+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation as the Duplicate Investigator,\
    \ I have completed the duplicate screening for OOMPAH-689. Let me provide my findings:\n\
    \n## Duplicate Screening Complete\n\n**Focus handoff: duplicate_detector**\n\n\
    **Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\n\
    \nConducted exhaustive search across all oompah task states:\n- `.oompah/tasks/open/`\
    \ \u2014 1 task (OOMPAH-281, self-hosted runner setup \u2014 unrelated)\n- `.oompah/tasks/merged/`\
    \ \u2014 7 tasks (OOMPAH-271, 272, 275, 277, 278, 279, 280 \u2014 all unrelated\
    \ to worker handoffs or peer scoping)\n- `.oompah/tasks/archived/` \u2014 200+\
    \ historical tasks with no mentions of: worker handoff integrity, peer scope denial,\
    \ cross-task authorization, task view authorization, 403 denials, or EXOCOMP projects\n\
    \nKeyword searches applied across all task files and code:\n- \"OOMPAH-678\",\
    \ \"EXOCOMP-155\", \"verified_peer\", \"task_handoff\", \"worker_exit\", \"_is_verified_peer_scope_denial\"\
    \ \u2192 no results\n- \"poison\", \"scope_denial\", \"read_only\", \"cross_task\"\
    , \"reconciliation\" \u2192 no results\n- \"HTTP.403\", \"Needs_Human\", \"Ready.to.Integrate\"\
    , \"authorization_deny\" \u2192 no results\n\n**Closest reviewed task:** OOMPAH-281\
    \ (completely unrelated \u2014 GitHub Actions runner setup, not handoff authorization).\n\
    \nThis is the first issue filed concerning worker handoff security regressions\
    \ from cross-task peer-scope authorization denials. OOMPAH-689 is a unique, novel\
    \ problem that has not been previously tracked in this project."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4175bc24-7883-4cc9-ae35-68cb69c32439
oompah.task_costs:
  total_input_tokens: 18049140
  total_output_tokens: 48456
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 18049056
      output_tokens: 40431
      cost_usd: 0.0
    unknown:
      input_tokens: 84
      output_tokens: 8025
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 154
    output_tokens: 4433
    cost_usd: 0.0
    recorded_at: '2026-08-02T00:15:10.972539+00:00'
  - profile: default
    model: haiku
    input_tokens: 18048902
    output_tokens: 35998
    cost_usd: 0.0
    recorded_at: '2026-08-02T00:31:34.385291+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 33
    output_tokens: 6517
    cost_usd: 0.0
    recorded_at: '2026-08-02T00:57:40.731608+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 51
    output_tokens: 1508
    cost_usd: 0.0
    recorded_at: '2026-08-02T01:03:31.882086+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-689__20260802T001348Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-689
    source_sha: e613933ecf228bc89afb98df63e584eab21a50a9
    completed_at: '2026-08-02T00:15:10.985196+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-689
  head_sha: a5acdde6497e03bb83714ec585dff131b4b09398
  submitted_at: '2026-08-02T00:31:02.843059+00:00'
  updated_at: '2026-08-02T00:31:02.843059+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/648
oompah.review_number: '648'
oompah.work_branch: OOMPAH-689
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-68276aa50ebb: '2026-08-02T00:57:25.104904+00:00'
    attempt-9dd1c98988ea: '2026-08-02T01:03:08.953282+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-689
    target_state: Done
    evidence_fingerprint: 885db9c57a581ef3a742173d863ce064b260ce60f7b056161d52cafdbf9fa7b7
    audit_ids:
    - audit-b7a055e8c647
    kind: result
    applied: true
    retired_at: '2026-08-02T00:57:25.104915+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-689
    target_state: Merged
    evidence_fingerprint: 885db9c57a581ef3a742173d863ce064b260ce60f7b056161d52cafdbf9fa7b7
    audit_ids:
    - audit-a10f3199dad8
    kind: result
    applied: true
    retired_at: '2026-08-02T01:03:08.953299+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-689
    audit_id: audit-b7a055e8c647
    attempt_id: attempt-68276aa50ebb
    target_state: Done
    evidence_fingerprint: 885db9c57a581ef3a742173d863ce064b260ce60f7b056161d52cafdbf9fa7b7
    status: In Validation
    audit_ids:
    - audit-b7a055e8c647
    applied: true
    created_at: '2026-08-02T00:57:25.104930+00:00'
    applied_at: '2026-08-02T00:57:28.447624+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-689
    audit_id: audit-a10f3199dad8
    attempt_id: attempt-9dd1c98988ea
    target_state: Merged
    evidence_fingerprint: 885db9c57a581ef3a742173d863ce064b260ce60f7b056161d52cafdbf9fa7b7
    status: Merged
    audit_ids:
    - audit-a10f3199dad8
    applied: true
    created_at: '2026-08-02T01:03:08.953320+00:00'
    applied_at: '2026-08-02T01:03:13.701965+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-b7a055e8c647
    project_id: proj-14849f1b
    task_id: OOMPAH-689
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 885db9c57a581ef3a742173d863ce064b260ce60f7b056161d52cafdbf9fa7b7
    attempts:
    - version: 1
      attempt_id: attempt-68276aa50ebb
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 885db9c57a581ef3a742173d863ce064b260ce60f7b056161d52cafdbf9fa7b7
      created_at: '2026-08-02T00:51:50.245041+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T00:51:50.245041+00:00'
      branch_key: OOMPAH-689
      verdict: pass
      completed_at: '2026-08-02T00:57:25.104670+00:00'
      ended_at: '2026-08-02T00:57:25.104670+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T00:51:24.042669+00:00'
    updated_at: '2026-08-02T00:57:25.104670+00:00'
  - version: 1
    audit_id: audit-a10f3199dad8
    project_id: proj-14849f1b
    task_id: OOMPAH-689
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 885db9c57a581ef3a742173d863ce064b260ce60f7b056161d52cafdbf9fa7b7
    attempts:
    - version: 1
      attempt_id: attempt-9dd1c98988ea
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 885db9c57a581ef3a742173d863ce064b260ce60f7b056161d52cafdbf9fa7b7
      created_at: '2026-08-02T00:58:53.940908+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T00:58:53.940908+00:00'
      branch_key: OOMPAH-689
      verdict: pass
      completed_at: '2026-08-02T01:03:08.953008+00:00'
      ended_at: '2026-08-02T01:03:08.953008+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T00:51:24.042669+00:00'
    updated_at: '2026-08-02T01:03:08.953008+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-68276aa50ebb
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 885db9c57a581ef3a742173d863ce064b260ce60f7b056161d52cafdbf9fa7b7
    created_at: '2026-08-02T00:51:50.245041+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T00:51:50.245041+00:00'
    branch_key: OOMPAH-689
  - version: 1
    attempt_id: attempt-9dd1c98988ea
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 885db9c57a581ef3a742173d863ce064b260ce60f7b056161d52cafdbf9fa7b7
    created_at: '2026-08-02T00:58:53.940908+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T00:58:53.940908+00:00'
    branch_key: OOMPAH-689
---
## Summary

Live regression on EXOCOMP-155 on 2026-08-01/02 after merged OOMPAH-678. The worker successfully viewed, commented on, and submitted its assigned task, but also attempted read-only oompah task view calls for related non-running Exocomp tasks. Those calls correctly returned scoped HTTP 403. At worker exit, Oompah nevertheless consumed a recorded task-handoff failure, overwrote the successful Ready-to-Integrate submission with Needs Human, and claimed the task-scoped capability could not update the task.

Root cause: server._is_verified_peer_scope_denial verifies both the source worker and the target with _verified_running_entry. OOMPAH-678 therefore treats read-only exploration as informational only when the target task happens to be running; an Open, Ready-to-Integrate, Done, or otherwise non-running peer produces record_task_handoff_failure, even though the source assignment/token is verified and its own-task mutations succeed.

Implementation scope:
- Classify a read-only cross-task view denial from a verified live source worker as an intentional policy denial without requiring the target task to have a RunningEntry.
- Keep authorization fail-closed: the peer request remains HTTP 403 and returns no task data.
- Do not suppress wrong-token propagation, missing/expired/revoked capabilities, cross-project ambiguity, or forbidden cross-task mutations.
- Make worker-exit reconciliation distinguish informational denials from failures of the assigned task's own handoff operations. A successful own-task submit must not be overwritten by earlier expected peer-read denials.
- Preserve actionable auth-health counters for genuine mismatches and informational policy counters for expected exploration.

Relevant code: oompah/server.py (_is_verified_peer_scope_denial and task-handoff validation), oompah/task_handoff.py failure recording, and oompah/orchestrator.py worker-exit handoff reconciliation.

Required tests:
- A verified worker views a non-running sibling, receives 403, then comments on and submits its assigned task; exit leaves the task submitted and never Needs Human.
- The same sequence covers Open, Ready-to-Integrate, terminal, and unknown target identifiers without leaking existence.
- Wrong-token use against the assigned task and cross-task mutation attempts remain rejected and retain the intended actionable signal.
- OOMPAH-678 live-peer behavior and auth-health tests remain green.

Acceptance criteria:
- Replaying the EXOCOMP-155 request sequence cannot overwrite a successful submit with Needs Human.
- Expected peer reads stay fail-closed but do not degrade handoff health or poison exit reconciliation.
- Focused task-handoff/server/orchestrator tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 00:13
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 00:13
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 00:15
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 40, Tool calls: 18
- Tokens: 154 in / 4.4K out [4.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 26s
- Log: OOMPAH-689__20260802T001348Z.jsonl
---
author: oompah
created: 2026-08-02 00:15
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-02 00:15
---
Focus: Callback Auth Validation Specialist
---
author: oompah
created: 2026-08-02 00:15
---
Understanding: verified workers must keep non-running cross-task views fail-closed (403) while treating them as informational; own-task handoff failures and security-relevant mismatches must remain actionable. I will inspect server classification, task-handoff recording, and orchestrator exit reconciliation, then add regression coverage for target states and forbidden mutations.
---
author: oompah
created: 2026-08-02 00:30
---
Discovery: OOMPAH-678's _is_verified_peer_scope_denial required a second _verified_running_entry for the target, so expected peer views of non-running or unknown tasks were recorded as handoff failures. Scope-reason matching also included project denials and all actions, which could suppress security signals.
---
author: oompah
created: 2026-08-02 00:30
---
Implementation: server peer classification now verifies only the live source capability in the requested project, requires the exact task-scope denial and view action, and never resolves the target. Added lifecycle/unknown, mutation, cross-project, wrong-token, and successful comment-submit-exit regressions; clarified actionable-only handoff failure reconciliation and updated auth documentation.
---
author: oompah
created: 2026-08-02 00:30
---
Verification: focused handoff/auth/server suites pass: 171 passed, 1 deprecation warning. make check-secrets passes. The required full make test could not start because the environment's uv launcher fails to create a transient DBus scope; the direct project serial runner reached the full suite but exposed unrelated pre-existing ACP model-handoff failures before I stopped it. git diff --check is clean.
---
author: oompah
created: 2026-08-02 00:30
---
Completion: delivered and pushed commit a5acdde6497e03bb83714ec585dff131b4b09398. Verified peer view denials remain HTTP 403 without target resolution or handoff-failure recording, while own comment/submit and exit reconciliation preserve Ready to Integrate; actionable auth and mutation paths remain covered. Focused suites and secret scan pass; full make test remains environment-blocked by the uv/DBus launcher failure noted above.
---
author: oompah
created: 2026-08-02 00:31
---
Preserve successful task handoff after informational non-running peer reads; added fail-closed/auth-health and exit-reconciliation regressions.
---
author: oompah
created: 2026-08-02 00:31
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 107
- Tokens: 18.0M in / 36.0K out [18.1M total]
- Cost: $0.0000
- Exit: terminated, Duration: 16m 8s
- Log: OOMPAH-689__20260802T001529Z.jsonl
---
author: oompah
created: 2026-08-02 00:38
---
Branch quality gate passed for `a5acdde6497e03bb83714ec585dff131b4b09398` using `make test` in 391.4s. Review creation may proceed.
---
author: oompah
created: 2026-08-02 00:51
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-02 00:51
---
YOLO: merged PR #648.
---
author: oompah
created: 2026-08-02 00:51
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 00:51
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 00:57
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: a5acdde6497e03bb83714ec585dff131b4b09398
- merge_commit: 431d472825a0dc7eeb75a9489ef4f91e9599db15
- pr_number: 648
- files_changed: docs/authentication.md, docs/scoped-task-cli-authentication.md, oompah/auth_health.py, oompah/orchestrator.py, oompah/server.py, oompah/task_handoff.py, tests/test_task_handoff.py
- diff_stat: 7 files changed, 391 insertions(+), 24 deletions(-)
- focused_tests_task_handoff: 68 passed in 10.62s
- focused_tests_handoff_auth_server: 171 passed, 1 deprecation warning in 12.92s
- focused_tests_orchestrator_handlers: 277 passed in 166.72s
- branch_gate_make_test: passed in 391.4s (per branch quality gate comment)
- regression_test_added: TestFailedHandoffLifecycle::test_informational_peer_read_does_not_poison_successful_submit (asserts Ready to Integrate preserved through exit reconciliation)
- parametrized_peer_view_states: Open, Ready to Integrate, Done, Unknown (target never resolved; policy_denial_count == 1, recent_403_scope_count == 0)
- parametrized_mutation_actionable: comment, submit (recent_403_scope_count == 1, policy_denial_count == 0, actionable failure recorded)
- [REDACTED-credential-key]: test_wrong_token_targeting_assigned_task_remains_auth_failure asserts scope alert + actionable failure
- cross_project_denial_preserved: test_wrong_project_token_returns_403 asserts scope alert + actionable failure
- commit_trailer: canonical oompah trailer, no model attribution
---
author: oompah
created: 2026-08-02 00:57
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 35, Tool calls: 27
- Tokens: 33 in / 6.5K out [6.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 49s
- Log: OOMPAH-689__20260802T005155Z.jsonl
---
author: oompah
created: 2026-08-02 00:58
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 00:58
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:03
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- branch_head: a5acdde6497e03bb83714ec585dff131b4b09398
- merge_commit: 431d472825a0dc7eeb75a9489ef4f91e9599db15
- pr_number: 648
- files_changed: docs/authentication.md, docs/scoped-task-cli-authentication.md, oompah/auth_health.py, oompah/orchestrator.py, oompah/server.py, oompah/task_handoff.py, tests/test_task_handoff.py
- diff_stat: 7 files changed, 391 insertions(+), 24 deletions(-)
- focused_tests_task_handoff_rerun: 68 passed in 7.07s at HEAD a5acdde64
- focused_tests_handoff_auth_server_rerun: 171 passed, 1 deprecation warning in 8.07s at HEAD a5acdde64
- focused_tests_orchestrator_handlers_rerun: 277 passed in 85.31s at HEAD a5acdde64
- branch_gate_make_test: passed in 391.4s (per branch quality gate comment for a5acdde64)
- regression_test_present: TestFailedHandoffLifecycle::test_informational_peer_read_does_not_poison_successful_submit
- parametrized_peer_view_states_present: Open, Ready to Integrate, Done, Unknown; tracker.fetch_issue_detail.side_effect asserts target must not be resolved
- parametrized_mutation_actionable_present: comment, submit; asserts recent_403_scope_count==1 and consume_task_handoff_failure returns record
- cross_project_denial_actionable: test_wrong_project_token_returns_403 asserts scope alert + actionable failure
- peer_view_never_resolves_target: server._is_verified_peer_scope_denial deliberately does not call _verified_running_entry on target; only accepts action=='view'
- exit_reconciler_actionable_only: [REDACTED-credential-pattern] renames handoff_failure -> actionable_handoff_failure with comment clarifying registry semantics
- commit_trailer: canonical oompah trailer, no model attribution
---
author: oompah
created: 2026-08-02 01:03
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 27
- Tokens: 51 in / 1.5K out [1.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 37s
- Log: OOMPAH-689__20260802T005900Z.jsonl
---
<!-- COMMENTS:END -->
