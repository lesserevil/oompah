---
id: OOMPAH-647
type: task
status: In Validation
priority: null
title: Make merge-conflict rebase continuation noninteractive and deadlock-safe
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T07:09:27.752943Z'
updated_at: '2026-07-31T08:54:39.948430Z'
work_branch: OOMPAH-647
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/612
review_number: '612'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 68fcb9c97245c8ffaa75c53536a9ffa3c84fea1bb8ec55c467315ac0a4a26565
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T07:10:54.566738+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Only active native task is OOMPAH-281, covering a self-hosted CI runner.
    Closest matches OOMPAH-214 (Archived, conflict-agent dispatch) and OOMPAH-235
    (Archived, tracker rebase recovery) are terminal and do not cover noninteractive
    rebase continuation/editor deadlock prevention.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: f04374c6-0574-41a8-8715-8a7b627a01d5
oompah.task_costs:
  total_input_tokens: 269913
  total_output_tokens: 43519
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 269870
      output_tokens: 36312
      cost_usd: 0.0
    unknown:
      input_tokens: 43
      output_tokens: 7207
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 269782
    output_tokens: 1487
    cost_usd: 0.0
    recorded_at: '2026-07-31T07:10:54.563272+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 88
    output_tokens: 34825
    cost_usd: 0.0
    recorded_at: '2026-07-31T07:25:32.013615+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 43
    output_tokens: 7207
    cost_usd: 0.0
    recorded_at: '2026-07-31T08:07:16.425874+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-647__20260731T070958Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: duplicate_detector
    source_branch: OOMPAH-647
    source_sha: 50625abed5be36e106dbd281871a2e464c671303
    completed_at: '2026-07-31T07:10:54.580031+00:00'
  - run_id: OOMPAH-647__20260731T071117Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: sonnet
    focus: merge_conflict
    source_branch: OOMPAH-647
    source_sha: 79fbad71a4c5e735916e16db6fd546d455da3022
    completed_at: '2026-07-31T07:25:32.018503+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-647
  base_branch: main
  base_sha: d48b971c58b8622e9c63de4923db08b755b5434b
  head_sha: 79fbad71a4c5e735916e16db6fd546d455da3022
  submitted_at: '2026-07-31T07:25:16.774548+00:00'
  updated_at: '2026-07-31T07:25:34.003940+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/612
oompah.review_number: '612'
oompah.work_branch: OOMPAH-647
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-d19fa24aa57b: '2026-07-31T08:07:04.573902+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c373f00a8724
    project_id: proj-14849f1b
    task_id: OOMPAH-647
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e30399b1964001c7e507aa7e9f3b8938b03bf4af6c5dc92fa2fa919bd6bef47b
    attempts:
    - version: 1
      attempt_id: attempt-d19fa24aa57b
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e30399b1964001c7e507aa7e9f3b8938b03bf4af6c5dc92fa2fa919bd6bef47b
      created_at: '2026-07-31T08:03:45.938278+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T08:03:45.938278+00:00'
      branch_key: OOMPAH-647
      verdict: pass
      completed_at: '2026-07-31T08:07:04.573791+00:00'
      ended_at: '2026-07-31T08:07:04.573791+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T07:54:50.402416+00:00'
    updated_at: '2026-07-31T08:07:04.573791+00:00'
  - version: 1
    audit_id: audit-dcbc7765d0dc
    project_id: proj-14849f1b
    task_id: OOMPAH-647
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e30399b1964001c7e507aa7e9f3b8938b03bf4af6c5dc92fa2fa919bd6bef47b
    attempts:
    - version: 1
      attempt_id: attempt-122c4fbfae2d
      target_state: Merged
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e30399b1964001c7e507aa7e9f3b8938b03bf4af6c5dc92fa2fa919bd6bef47b
      created_at: '2026-07-31T08:33:09.653124+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T08:33:09.653124+00:00'
      branch_key: OOMPAH-647
      ended_at: '2026-07-31T08:54:33.225813+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-7af68c392bdb
      target_state: Merged
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e30399b1964001c7e507aa7e9f3b8938b03bf4af6c5dc92fa2fa919bd6bef47b
      created_at: '2026-07-31T08:54:36.157806+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-07-31T08:54:36.157806+00:00'
      branch_key: OOMPAH-647
      candidate_rotation_count: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T07:54:50.402416+00:00'
    updated_at: '2026-07-31T08:54:36.157806+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-d19fa24aa57b
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e30399b1964001c7e507aa7e9f3b8938b03bf4af6c5dc92fa2fa919bd6bef47b
    created_at: '2026-07-31T08:03:45.938278+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T08:03:45.938278+00:00'
    branch_key: OOMPAH-647
  - version: 1
    attempt_id: attempt-122c4fbfae2d
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e30399b1964001c7e507aa7e9f3b8938b03bf4af6c5dc92fa2fa919bd6bef47b
    created_at: '2026-07-31T08:33:09.653124+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T08:33:09.653124+00:00'
    branch_key: OOMPAH-647
    ended_at: '2026-07-31T08:54:33.225813+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-7af68c392bdb
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e30399b1964001c7e507aa7e9f3b8938b03bf4af6c5dc92fa2fa919bd6bef47b
    created_at: '2026-07-31T08:54:36.157806+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-07-31T08:54:36.157806+00:00'
    branch_key: OOMPAH-647
    candidate_rotation_count: 1
---
## Summary

Live deadlock on 2026-07-31 while recovering OOMPAH-643/PR #610: the Merge Conflict Resolver correctly resolved and staged terminal_transition_coordinator.py, then ran 'git add ... && git rebase --continue'. Git spawned /usr/bin/vi on .git/worktrees/OOMPAH-643/COMMIT_EDITMSG and the ACP tool call blocked from 07:05:37 until the operator terminated only the editor PID at 07:08:40; the same agent then resumed and completed the rebase at 2b3a967c8. Implementation scope: ensure every server-generated merge/rebase continuation path is explicitly noninteractive (for example GIT_EDITOR=true/GIT_SEQUENCE_EDITOR=true or git -c core.editor=true as appropriate), preserves the original commit message and required attribution trailer, and cannot inherit an interactive editor from the host. Add bounded command monitoring so an unexpected editor/prompt is terminated and reported/retried without discarding staged conflict resolution. Cover resolver prompts, command wrappers/MCP policy, retry/recovery, and any automated rebase helpers. Required tests: real repository conflict with an unset editor; hostile EDITOR pointing to a blocking executable that must never be invoked; continuation success and preserved message/trailers; unexpected prompt timeout retains recoverable rebase state; repeated recovery is idempotent. Acceptance: OOMPAH-643-style rebase continuation completes unattended, no vi/editor child can deadlock an agent slot, focused conflict-resolver/process tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 07:09
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-31 07:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 07:10
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 6
- Tokens: 269.8K in / 1.5K out [271.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 5s
- Log: OOMPAH-647__20260731T070958Z.jsonl
---
author: oompah
created: 2026-07-31 07:11
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-31 07:11
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-07-31 07:15
---
**Understanding**: OOMPAH-643 deadlock: the merge-conflict resolver ran 'git rebase --continue' which caused git to spawn /usr/bin/vi on the COMMIT_EDITMSG, blocking the ACP tool call for ~3 minutes until the operator killed the editor PID.\n\n**Planned approach:**\n1. Create `oompah/git_noninteractive.py` with a `NONINTERACTIVE_GIT_ENV` dict (`GIT_EDITOR=true`, `GIT_SEQUENCE_EDITOR=true`, `GIT_TERMINAL_PROMPT=0`) and a `run_rebase_continue()` helper with bounded subprocess timeout/kill monitoring.\n2. Update `oompah/integration_executor.py` `_git()` to always pass `NONINTERACTIVE_GIT_ENV` so the server-side rebase operations can never spawn an editor.\n3. Update `oompah/cherry_pick_pr_creator.py` subprocess calls to also pass noninteractive env.\n4. Update `oompah/focus.py` merge_conflict focus must_do list to instruct agents to use `GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true` before `git rebase --continue`.\n5. Add `tests/test_git_noninteractive.py` with the five required test scenarios.\n\n**Key insight**: The fix has two layers — (a) server-side subprocess calls must set noninteractive env, (b) the agent prompt instructions must tell agents to use the same env when they run git commands.
---
author: oompah
created: 2026-07-31 07:15
---
**Discovery**: Found the key locations that need changes:\n\n1. `oompah/integration_executor.py` L30-39: `_git()` function uses bare `subprocess.run(['git', ...])` with no environment override — any `EDITOR` var from the host can be inherited\n2. `oompah/focus.py` L468-491: `merge_conflict` focus `must_do` list does not mention using `GIT_EDITOR=true` before `git rebase --continue`\n3. `oompah/cherry_pick_pr_creator.py` L267,312,339: multiple subprocess git calls also inherit host env\n\nNo existing `GIT_EDITOR` or `GIT_SEQUENCE_EDITOR` references anywhere in the codebase. Creating new module `oompah/git_noninteractive.py` as the canonical fix point.
---
author: oompah
created: 2026-07-31 07:24
---
**Implementation**: Created `oompah/git_noninteractive.py` with `NONINTERACTIVE_GIT_ENV` dict and `run_rebase_continue()` helper. Updated `integration_executor._git()` and all `cherry_pick_pr_creator` subprocess calls to pass noninteractive env. Updated `focus.py` merge_conflict focus with explicit GIT_EDITOR=true instruction and prohibition on bare 'git rebase --continue'. Added 18 tests covering all 5 acceptance criteria. Updated 2 existing test files to account for changed call signatures/wording.
---
author: oompah
created: 2026-07-31 07:25
---
**Verification**: All 230 tests pass across the 5 affected suites (test_git_noninteractive: 18 new tests, test_integration_executor: 7, test_integration_conflict_repair: 9, test_cherry_pick_pr_creator: 58, test_focus: 138). All 5 acceptance criteria verified by test:\n- AC1: Real conflict + unset editor → rebase --continue succeeds\n- AC2: Hostile EDITOR never invoked\n- AC3: Commit message + attribution trailer preserved\n- AC4: Timeout kill leaves REBASE_HEAD intact\n- AC5: Repeated recovery is idempotent\n\nBranch pushed: 79fbad71a
---
author: oompah
created: 2026-07-31 07:25
---
**Completion**: Delivered OOMPAH-647 (Make merge-conflict rebase continuation noninteractive and deadlock-safe).\n\nFiles changed:\n- `oompah/git_noninteractive.py` (new): NONINTERACTIVE_GIT_ENV, run_git_noninteractive(), run_rebase_continue() with bounded process-group kill, _is_rebase_in_progress()\n- `oompah/integration_executor.py`: _git() now passes NONINTERACTIVE_GIT_ENV to all git subprocess calls\n- `oompah/cherry_pick_pr_creator.py`: All 6 git subprocess calls now pass noninteractive env\n- `oompah/focus.py`: merge_conflict focus updated with GIT_EDITOR=true must_do and must_not_do\n- `tests/test_git_noninteractive.py` (new): 18 tests covering all 5 AC\n- `tests/test_cherry_pick_pr_creator.py`: Updated 2 exact-call assertions\n- `tests/test_focus.py`: Updated 2 wording assertions\n\nThe OOMPAH-643 deadlock is now prevented at two layers: (1) server-side subprocess calls force GIT_EDITOR=true via env, (2) agent instructions in merge_conflict focus explicitly prohibit bare 'git rebase --continue'.
---
author: oompah
created: 2026-07-31 07:25
---
Added oompah/git_noninteractive.py with NONINTERACTIVE_GIT_ENV dict and run_rebase_continue() with bounded process-group kill. Updated integration_executor._git() and all cherry_pick_pr_creator subprocess calls to pass noninteractive env. Updated merge_conflict focus in focus.py with GIT_EDITOR=true instructions. Added 18 tests covering all 5 acceptance criteria (real conflict, hostile editor, message preservation, timeout recovery, idempotency).
---
author: oompah
created: 2026-07-31 07:25
---
Agent completed successfully in 866s (34913 tokens)
---
author: oompah
created: 2026-07-31 07:25
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 156, Tool calls: 103
- Tokens: 88 in / 34.8K out [34.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 14m 26s
- Log: OOMPAH-647__20260731T071117Z.jsonl
---
author: oompah
created: 2026-07-31 07:47
---
Branch quality gate passed for `79fbad71a4c5e735916e16db6fd546d455da3022` using `make test` in 270.4s. Review creation may proceed.
---
author: oompah
created: 2026-07-31 07:54
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 07:54
---
YOLO: merged PR #612.
---
author: oompah
created: 2026-07-31 08:03
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 08:03
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 08:07
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: 79fbad71a4c5e735916e16db6fd546d455da3022
- merged_into_main_via: PR #612 (a95fac583)
- test_git_noninteractive: 18 passed
- test_integration_executor: 7 passed
- test_cherry_pick_pr_creator: 53 passed
- test_focus: 138 passed
- test_integration_conflict_repair: 14 passed
- branch_gate: make test passed in 270.4s (recorded in comments)
- noninteractive_env_vars: GIT_EDITOR, GIT_SEQUENCE_EDITOR, GIT_TERMINAL_PROMPT, GIT_ASKPASS, GIT_SSH_COMMAND
- callsites_wired: integration_executor._git, cherry_pick_pr_creator (6 sites), focus.merge_conflict must_do/must_not_do
---
author: oompah
created: 2026-07-31 08:07
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 47, Tool calls: 37
- Tokens: 43 in / 7.2K out [7.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 28s
- Log: OOMPAH-647__20260731T080353Z.jsonl
---
author: oompah
created: 2026-07-31 08:33
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 08:33
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 08:54
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-07-31 08:54
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
