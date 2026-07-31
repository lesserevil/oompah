---
id: OOMPAH-649
type: task
status: Merged
priority: null
title: Preserve dirty task worktrees across worker termination and retry
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T07:19:33.053515Z'
updated_at: '2026-07-31T09:44:36.275531Z'
work_branch: OOMPAH-649
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/615
review_number: '615'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 34b7218c890759bfab1fc1575e53815c1060649d03e9dae5e880401024c8464e
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T07:22:29.514613+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation, I have:\n\n1. \u2705 Searched\
    \ all active tasks (open, backlog) - found OOMPAH-281 (unrelated: containerized\
    \ runner) and OOMPAH-282 (unrelated: Unicode encoding bug)\n2. \u2705 Searched\
    \ merged/archived task histories - no duplicates matching worktree preservation\n\
    3. \u2705 Searched docs/ and plans/ directories - no existing documentation on\
    \ this topic\n4. \u2705 Searched for references to OOMPAH-644 and OOMPAH-645 mentioned\
    \ in the description - they do not exist as tracked tasks\n5. \u2705 Searched\
    \ for related keywords (dirty, worktree, termination, cleanup, retry, preserve,\
    \ reset, stash, recovery) - no active duplicate tasks found\n\n## Investigation\
    \ Summary\n\n**OOMPAH-649** addresses a critical data-loss bug: when a worker\
    \ is terminated with `cleanup=False` during task work, the subsequent retry launch\
    \ starts on a clean worktree with the previous agent's staged/unstaged/untracked\
    \ changes completely lost. The issue description references OOMPAH-644 and OOMPAH-645\
    \ as prior instances of this data loss, but these are not currently tracked as\
    \ separate active tasks \u2014 they're mentioned only as context for the problem.\n\
    \nThe required fix involves:\n- Detecting dirty worktrees before any reset/sync/rebase\n\
    - Preserving changes durably via task-scoped recovery commits or snapshots\n-\
    \ Exposing recovery context and exact prior filesystem state to retry agents\n\
    - Preventing silent data loss via `reset --hard`\n\nThis is a unique, previously-unaddressed\
    \ task with no active duplicate.\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\
    \ Searched all task states (open, backlog, merged, archived), docs/, plans/, and\
    \ entire repository for related keywords (dirty, worktree, termination, cleanup,\
    \ retry, preserve, reset, stash, recovery, worker). Only active tasks are OOMPAH-281\
    \ (self-hosted runner) and OOMPAH-282 (Unicode encoding bug), both unrelated.\
    \ OOMPAH-649 is a unique task addressing a critical data-loss b"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 89318e91-c940-4206-8649-a4c23121637d
oompah.task_costs:
  total_input_tokens: 215
  total_output_tokens: 15888
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 146
      output_tokens: 3808
      cost_usd: 0.0
    unknown:
      input_tokens: 69
      output_tokens: 12080
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 146
    output_tokens: 3808
    cost_usd: 0.0
    recorded_at: '2026-07-31T07:22:29.513382+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 69
    output_tokens: 12080
    cost_usd: 0.0
    recorded_at: '2026-07-31T09:16:16.636130+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-649__20260731T072014Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-649
    source_sha: d48b971c58b8622e9c63de4923db08b755b5434b
    completed_at: '2026-07-31T07:22:29.525605+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-649
  head_sha: 0957d99556f3200361fa225ba313a7b5db53daa6
  submitted_at: '2026-07-31T08:54:15.875304+00:00'
  updated_at: '2026-07-31T08:54:15.875304+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/615
oompah.review_number: '615'
oompah.work_branch: OOMPAH-649
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-2ae62c68e14f: '2026-07-31T09:16:02.914959+00:00'
    attempt-10e9d1bb1126: '2026-07-31T09:44:33.134339+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-4e11fcd2a697
    project_id: proj-14849f1b
    task_id: OOMPAH-649
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5c7c785b0ad9de53a432a8fab0781ca91d005931a783046c2586155076f0efc7
    attempts:
    - version: 1
      attempt_id: attempt-2ae62c68e14f
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 5c7c785b0ad9de53a432a8fab0781ca91d005931a783046c2586155076f0efc7
      created_at: '2026-07-31T09:09:21.680144+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T09:09:21.680144+00:00'
      branch_key: OOMPAH-649
      verdict: pass
      completed_at: '2026-07-31T09:16:02.914804+00:00'
      ended_at: '2026-07-31T09:16:02.914804+00:00'
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T09:09:10.429787+00:00'
    updated_at: '2026-07-31T09:16:02.914804+00:00'
  - version: 1
    audit_id: audit-1e014b11292a
    project_id: proj-14849f1b
    task_id: OOMPAH-649
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5c7c785b0ad9de53a432a8fab0781ca91d005931a783046c2586155076f0efc7
    attempts:
    - version: 1
      attempt_id: attempt-10e9d1bb1126
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 5c7c785b0ad9de53a432a8fab0781ca91d005931a783046c2586155076f0efc7
      created_at: '2026-07-31T09:39:42.952952+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T09:39:42.952952+00:00'
      branch_key: OOMPAH-649
      verdict: pass
      completed_at: '2026-07-31T09:44:33.134148+00:00'
      ended_at: '2026-07-31T09:44:33.134148+00:00'
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T09:09:10.429787+00:00'
    updated_at: '2026-07-31T09:44:33.134148+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-2ae62c68e14f
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5c7c785b0ad9de53a432a8fab0781ca91d005931a783046c2586155076f0efc7
    created_at: '2026-07-31T09:09:21.680144+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T09:09:21.680144+00:00'
    branch_key: OOMPAH-649
  - version: 1
    attempt_id: attempt-10e9d1bb1126
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5c7c785b0ad9de53a432a8fab0781ca91d005931a783046c2586155076f0efc7
    created_at: '2026-07-31T09:39:42.952952+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T09:39:42.952952+00:00'
    branch_key: OOMPAH-649
---
## Summary

Live data-loss reproduction on 2026-07-31: OOMPAH-645's first worker produced and focused-tested 317 lines across terminal_audit_health.py, orchestrator.py, dashboard.html, and three test files; the operator verified those modifications in the managed worktree. The healthy pytest child was then false-stall terminated with cleanup=False at 07:13:42. Before retry launch, managed worktree reflog recorded 'HEAD@{07:14:19}: reset: moving to HEAD'; the second agent started on a clean 1dc3f53e5 tree with no task commit or stash and had to reimplement the work. OOMPAH-644 similarly entered retry after a reset and reconstructed preserved intent. Implementation scope: worker retry preparation must never discard staged, unstaged, or untracked task-owned changes. Before any reset/sync/rebase, detect dirtiness and preserve it durably via a task-scoped recovery commit/ref or equivalent atomic snapshot; preferably reuse the dirty worktree directly when the branch/head authority still matches. A new attempt must receive explicit recovery context and the exact prior filesystem state. Fail closed on snapshot failure and route to Needs Human rather than running reset --hard. Terminal cleanup may remove a worktree only after committed/pushed/merged evidence or an explicit owner-approved disposition. Relevant files: Projects.ensure/create/reset worktree paths, retry dispatch, agent termination cleanup, branch synchronization, recovery metadata, and hygiene classification. Required tests: abrupt worker termination with staged, unstaged, and untracked edits; cleanup=False retry; process restart before retry; base branch advances; snapshot failure; repeated retry idempotency; terminal cleanup; cross-task isolation. Acceptance: an OOMPAH-645-style retry exposes byte-identical prior edits to the next agent with durable recovery evidence, no task work is silently reset, focused worktree/retry tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 07:19
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 07:19
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 07:22
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 40, Tool calls: 17
- Tokens: 146 in / 3.8K out [4.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 37s
- Log: OOMPAH-649__20260731T072014Z.jsonl
---
author: oompah
created: 2026-07-31 08:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 08:04
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-31 08:31
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 92
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 27m 33s
- Log: OOMPAH-649__20260731T080428Z.jsonl
---
author: oompah
created: 2026-07-31 08:33
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 08:34
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-31 08:34
---
Operator claim after old-runtime false-stall termination: the agent's complete dirty worktree is intact and anchored at recovery ref 33e1f9cc22a5. Holding dispatch while the operator commits, rebases, verifies, pushes, and submits this branch; the currently running server cannot safely retry this task until this fix is integrated.
---
author: oompah
created: 2026-07-31 08:34
---
Moved to Needs Human from the dashboard/API. Human action required: inspect OOMPAH-649 (Preserve dirty task worktrees across worker termination and retry), add the specific decision, missing information, or manual fix needed, then move the task back to Open when it is ready for agents again.
---
author: oompah
created: 2026-07-31 08:34
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 25s
- Log: OOMPAH-649__20260731T083405Z.jsonl
---
author: oompah
created: 2026-07-31 08:54
---
Operator recovery complete. Preserved the terminated worker's exact dirty tree, hardened it for durable task-scoped recovery refs/commits, rebased onto origin/main, and pushed commit 0957d99556f3200361fa225ba313a7b5db53daa6 to origin/OOMPAH-649. Verification on the exact head: terminal mutation scan 6/6; focused recovery/integration/prompt/telemetry tests 195/195; exact full Makefile gate 14,254 passed, 7 skipped, 1 xfailed. The temporary local operator recovery ref was removed only after the branch push. Returning this task to normal submission/audit flow.
---
author: oompah
created: 2026-07-31 08:54
---
Preserved dirty task worktrees durably across termination, retry, restart, and base advance; added fail-closed cleanup guards, recovery context, cross-task isolation, and comprehensive regression coverage. Exact full gate: 14,254 passed. Branch origin/OOMPAH-649 at 0957d9955.
---
author: oompah
created: 2026-07-31 09:01
---
Deadlock recovery: the server reran the exact full gate successfully, but OOMPAH-652 terminated the live service at gate completion before the success callback/PR creation could persist. Since exact head 0957d9955 already has two complete green gates, the operator created the PR directly to resume at the normal review/merge stage; no quality requirement was bypassed.
---
author: oompah
created: 2026-07-31 09:09
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 09:09
---
YOLO: merged PR #615.
---
author: oompah
created: 2026-07-31 09:09
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 09:09
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 09:16
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: 0957d99556f3200361fa225ba313a7b5db53daa6
- merged_into_main_at: 72ed26d3777a42adc53a6a740713c83ca555984a
- pr: 615
- focused_tests_passed: 210/210 across projects+integration_executor+task_cost_telemetry+prompt+terminal_audit_scanner
- recovery_ref_pattern: refs/oompah/recovery/{sanitized}-{sha256[:16]}
---
author: oompah
created: 2026-07-31 09:16
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 75, Tool calls: 63
- Tokens: 69 in / 12.1K out [12.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 54s
- Log: OOMPAH-649__20260731T090926Z.jsonl
---
author: oompah
created: 2026-07-31 09:39
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 09:39
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 09:44
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- branch_head: 0957d99556f3200361fa225ba313a7b5db53daa6
- merge_commit: 72ed26d3777a42adc53a6a740713c83ca555984a
- pr: 615
- merge_parents: 8fd133e26aa2823ab68cde2a42b446933142b614,0957d99556f3200361fa225ba313a7b5db53daa6
- focused_tests_passed_projects: 100/100
- focused_tests_passed_prompt_cost_integration: 95/95
- focused_tests_passed_terminal_audit_scanner: 15/15
- focused_tests_total: 210/210
- recovery_ref_pattern: refs/oompah/recovery/{sanitized}-{sha256[:16]}
- core_api_symbols: _worktree_recovery_ref, _preserve_dirty_worktree_locked, worktree_recovery_context, preserve_worktree_changes, _assert_terminal_worktree_safe_locked
- diff_stat: 9 files changed, 1200 insertions(+), 9 deletions(-)
---
<!-- COMMENTS:END -->
