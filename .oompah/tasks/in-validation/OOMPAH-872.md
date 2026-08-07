---
id: OOMPAH-872
type: bug
status: In Validation
priority: 1
title: Resolve the service checkout to a safe management project for operational error
  filing
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T05:27:00.661610Z'
updated_at: '2026-08-07T10:17:37.098610Z'
work_branch: OOMPAH-872
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/737
review_number: '737'
review_head: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2cfe576018288934d70a7eab658c211eff3f8f9ee5438660a1072303e84d4ff3
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-07T07:17:59.454529+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active duplicate was confirmed. Closest reviewed tasks\u2014\
    OOMPAH-15 and OOMPAH-156\u2014are Archived and address different ErrorWatcher\
    \ behavior; OOMPAH-161 is also Archived and concerns project-name lookup, not\
    \ safe repository-identity resolution.\nFocus handoff: duplicate_detector  \n\
    Duplicate preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence: No active\
    \ duplicate was confirmed. Closest reviewed tasks\u2014OOMPAH-15 and OOMPAH-156\u2014\
    are Archived and address different ErrorWatcher behavior; OOMPAH-161 is also Archived\
    \ and concerns project-name lookup, not safe repository-identity resolution."
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
  total_input_tokens: 48008
  total_output_tokens: 226
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 47922
      output_tokens: 212
      cost_usd: 0.0
    unknown:
      input_tokens: 86
      output_tokens: 14
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 47922
    output_tokens: 212
    cost_usd: 0.0
    recorded_at: '2026-08-07T07:17:59.432425+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 86
    output_tokens: 14
    cost_usd: 0.0
    recorded_at: '2026-08-07T10:08:51.907691+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-872__20260807T071650Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-872
    source_sha: 45e2b83356dd041200d7cad0970c7e6f939dc757
    completed_at: '2026-08-07T07:17:59.496533+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-872
  head_sha: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
  submitted_at: '2026-08-07T08:48:59.903561+00:00'
  updated_at: '2026-08-07T08:48:59.903561+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/737
oompah.review_number: '737'
oompah.work_branch: OOMPAH-872
oompah.target_branch: main
oompah.review_head: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-5b3c5f4c2a0d
    project_id: proj-14849f1b
    task_id: OOMPAH-872
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 53a58cc7a12c31c8a9a7ae79fdb721edce406cf65b95a26d03d77407bc873f83
    attempts:
    - version: 1
      attempt_id: attempt-4f9386900ca5
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 53a58cc7a12c31c8a9a7ae79fdb721edce406cf65b95a26d03d77407bc873f83
      created_at: '2026-08-07T09:51:57.808049+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-07T09:51:57.808049+00:00'
      branch_key: OOMPAH-872
      selected_ref: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
      selected_sha: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
      ended_at: '2026-08-07T10:15:35.281700+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-9ddad95f09d6
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 53a58cc7a12c31c8a9a7ae79fdb721edce406cf65b95a26d03d77407bc873f83
      created_at: '2026-08-07T10:17:34.985930+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-07T10:17:34.985930+00:00'
      branch_key: OOMPAH-872
      selected_ref: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
      selected_sha: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
      candidate_rotation_count: 1
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-07T09:45:34.532405+00:00'
    selected_ref: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
    selected_sha: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
    updated_at: '2026-08-07T10:17:34.985930+00:00'
  - version: 1
    audit_id: audit-46b8ca9873dd
    project_id: proj-14849f1b
    task_id: OOMPAH-872
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 53a58cc7a12c31c8a9a7ae79fdb721edce406cf65b95a26d03d77407bc873f83
    attempts: []
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-07T09:45:34.532405+00:00'
    selected_ref: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
    selected_sha: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
  attempt_history:
  - version: 1
    attempt_id: attempt-4f9386900ca5
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 53a58cc7a12c31c8a9a7ae79fdb721edce406cf65b95a26d03d77407bc873f83
    created_at: '2026-08-07T09:51:57.808049+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-07T09:51:57.808049+00:00'
    branch_key: OOMPAH-872
    selected_ref: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
    selected_sha: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
    ended_at: '2026-08-07T10:15:35.281700+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-9ddad95f09d6
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 53a58cc7a12c31c8a9a7ae79fdb721edce406cf65b95a26d03d77407bc873f83
    created_at: '2026-08-07T10:17:34.985930+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-07T10:17:34.985930+00:00'
    branch_key: OOMPAH-872
    selected_ref: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
    selected_sha: 0458f8f72b38d61bf81f1629a3d050d51c25bc8d
    candidate_rotation_count: 1
---
## Summary

At service startup from /home/shedwards/src/oompah, the global backend/frontend ErrorWatcher cannot select a safe management tracker because the configured managed project repo_path is /home/shedwards/.oompah/repos/oompah. It therefore disables operational error-task creation even though the Oompah project is registered and project log watchers remain active. Implement identity-safe checkout-to-project resolution for service/runtime clones without weakening OOMPAH-511/OOMPAH-512/OOMPAH-514 fail-closed protections. Prefer durable canonical repository identity and explicit configured management-project authority over path coincidence; reject ambiguous or foreign matches. Relevant code: service startup ErrorWatcher wiring, project repository identity/path resolution, management tracker selection, startup health/alerts. Required tests: canonical service clone maps to the one configured Oompah project; cached mirror and agent worktree aliases resolve only with matching repository identity; ambiguous matches disable filing with an actionable diagnostic; foreign/unmanaged clones remain rejected; restart retains the mapping. Acceptance: the normal production checkout enables backend/frontend operational task filing to the intended project, while unsafe or ambiguous topologies still fail closed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 07:16
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 07:16
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 07:18
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 47.9K in / 212 out [48.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 47s
- Log: OOMPAH-872__20260807T071650Z.jsonl
---
author: oompah
created: 2026-08-07 07:26
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-07 07:26
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 07:26
---
Understanding: the service ErrorWatcher must map its runtime checkout to the explicitly configured Oompah management project using durable repository identity, while rejecting ambiguous or foreign matches and preserving fail-closed protections. I will trace startup wiring and project identity resolution, implement focused resolver changes, add regression tests for canonical/alias/ambiguous/foreign/restart cases, then run focused checks.
---
author: oompah
created: 2026-08-07 07:27
---
Discovery: Orchestrator._management_tracker_scope in oompah/orchestrator.py:3990-4022 uses exact workflow-root/path coincidence. The global tracker is deliberately fail-closed in managed mode, and server.set_orchestrator disables the global ErrorWatcher when this scope lookup raises. I will add durable git repository identity matching with explicit management-project authority and retain strict ambiguity/foreign rejection.
---
author: oompah
created: 2026-08-07 07:33
---
Implementation: added RepositoryIdentity/canonical_repository_identity/repository_identity_for_path in oompah/projects.py; updated Orchestrator._management_tracker_scope to require configured repo_url plus runtime/project checkout identity agreement, recognize independent clones and shared Git worktrees, and reject foreign/ambiguous matches. server.set_orchestrator now records an actionable management_tracker_resolution alert when global ErrorWatcher setup fails. Added tests/test_management_tracker_resolution.py covering canonical URLs, clone/worktree aliases, foreign and ambiguous topology, and restart mapping.
---
author: oompah
created: 2026-08-07 07:35
---
Verification: with the task-independent project venv, tests/test_management_tracker_resolution.py passes 6/6 and tests/test_managed_tracker_state_branch_guard.py passes 19/19. The first run caught a legacy local-path configuration case; the resolver now preserves only exact-checkout local-path authority while still requiring matching Git identity for aliases.
---
author: oompah
created: 2026-08-07 07:43
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 88
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 24s
- Log: OOMPAH-872__20260807T072617Z.jsonl
---
author: oompah
created: 2026-08-07 08:33
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-08-07 08:33
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 08:34
---
Understanding (continuation): I am resuming the preserved attempt #1 changes. I will audit the repository-identity and explicit management-project authority rules, reconcile the recovery snapshot with the branch, run focused resolver and neighboring fail-closed tests, fix any gaps, then commit, push, and submit.
---
author: oompah
created: 2026-08-07 08:37
---
Discovery (continuation): the preserved resolver is in the right startup path, but audit found two fail-closed gaps: the scp-style regex can consume http:// and git:// URLs, producing inconsistent canonical identities, and a runtime clone can currently match configured repo_url even when the registered project checkout cannot provide repository evidence. I will restrict scp parsing to true scheme-less syntax, normalize standard ports, require valid matching checkout identity for Git runtimes, and add regression coverage.
---
author: oompah
created: 2026-08-07 08:45
---
Verification: focused integration run passes 192/192 tests: tests/test_management_tracker_resolution.py, tests/test_managed_tracker_state_branch_guard.py, tests/test_projects.py, tests/test_epic_draft_migration.py, tests/test_release_pick_migration_startup.py, and tests/test_error_watcher_orchestrator.py. This covers operational watcher routing, state-branch isolation, project persistence/restart, and neighboring startup consumers.
---
author: oompah
created: 2026-08-07 08:45
---
Implementation: added credential-free canonical Git repository identities and local checkout inspection in oompah/projects.py; rewired Orchestrator._management_tracker_scope to authorize independent clones, cached mirrors, and shared worktrees only when configured/runtime/managed identity evidence agrees; retained the explicit local-repository compatibility path; and added an actionable startup alert when global ErrorWatcher filing is disabled. Regression coverage now includes URL transports/default ports, relative remotes, canonical clone, mirror, worktree, foreign, missing, ambiguous, startup, and restart cases.
---
author: oompah
created: 2026-08-07 08:48
---
Completion: delivered identity-safe operational tracker resolution at commit 0458f8f72. The production service clone can now select the one configured Oompah project across clone/mirror/worktree paths; ambiguous, foreign, invalid, or missing evidence disables filing and emits a redacted actionable alert. Focused suites pass 192/192, the dedicated resolver suite passes 12/12 after final alert-snapshot coverage, secret scanning passes, and origin/OOMPAH-872 is synchronized.
---
author: oompah
created: 2026-08-07 08:49
---
Resolved operational management-project selection with canonical repository identity checks, fail-closed ambiguity/foreign handling, actionable startup alerts, and clone/mirror/worktree/restart regression coverage. Focused tests: 192 passed; final resolver suite: 12 passed.
---
author: oompah
created: 2026-08-07 08:50
---
Run #3 [attempt=3, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 73
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 12s
- Log: OOMPAH-872__20260807T083359Z.jsonl
---
author: oompah
created: 2026-08-07 09:23
---
Branch quality gate passed for `0458f8f72b38d61bf81f1629a3d050d51c25bc8d` using `make test` in 669.0s. Review creation may proceed.
---
author: oompah
created: 2026-08-07 09:45
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-07 09:45
---
YOLO: merged PR #737.
---
author: oompah
created: 2026-08-07 09:52
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-07 09:52
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-07 10:08
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 4
- Tokens: 86 in / 14 out [100 total]
- Cost: $0.0000
- Exit: terminated, Duration: 16m 44s
- Log: OOMPAH-872__20260807T095239Z.jsonl
---
<!-- COMMENTS:END -->
