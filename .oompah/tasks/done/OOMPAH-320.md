---
id: OOMPAH-320
type: task
status: Done
priority: 1
title: Define a forge-neutral SCM and CI provider contract
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-319
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T20:33:50.132513Z'
updated_at: '2026-07-21T23:22:28.297517Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 313f237d-3001-4de3-8067-295699da5287
oompah.task_costs:
  total_input_tokens: 2390507
  total_output_tokens: 38464
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 2390507
      output_tokens: 38464
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 48
    output_tokens: 10293
    cost_usd: 0.0
    recorded_at: '2026-07-21T22:58:27.853891+00:00'
  - profile: standard
    model: unknown
    input_tokens: 1305551
    output_tokens: 11024
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:03:35.475640+00:00'
  - profile: deep
    model: unknown
    input_tokens: 1084856
    output_tokens: 4551
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:07:25.107502+00:00'
  - profile: default
    model: unknown
    input_tokens: 52
    output_tokens: 12596
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:22:25.883838+00:00'
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, Core architecture and interfaces.

Refactor SCMProvider and normalized review/CI types so GitHub and GitLab use one explicit contract. Cover review state, labels, comments, files, commits, branch head, commit CI status, review creation/rebase/merge/close, and ordinary auto-merge. Define passed, failed, pending, and unknown CI states plus structured capability warnings. Move shared consumers only to contract methods; retain GitHub behavior.

Do not add GitLab REST endpoint implementations beyond test doubles in this task.

Tests:
- Contract test fixtures run against a fake provider and existing GitHub provider.
- Missing optional capabilities degrade to unknown/warnings rather than exceptions.
- Existing review, release, YOLO, churn, and close-gate tests remain green.

Acceptance criteria:
- No workflow consumer needs GitHub-specific provider methods for supported behavior.
- Contract documents error and unavailable-capability semantics in code.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 22:47
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 22:48
---
Understanding: Investigating OOMPAH-320 as Duplicate Investigator. This task asks for a forge-neutral SCM and CI provider contract refactor (SCMProvider, normalized review/CI types for GitHub + GitLab). Searching for any existing tasks that cover the same ground before any implementation begins.
---
author: oompah
created: 2026-07-21 22:58
---
Focus handoff: duplicate_detector

1. Outcome: OOMPAH-320 is NOT a duplicate. Duplicate screening complete.

Candidates searched and reviewed:
- Searched all tasks in .oompah/tasks/ (main branch: OOMPAH-1 through OOMPAH-282) for SCMProvider, forge-neutral, provider contract, gitlab, CI state, CIState, and review contract — zero matches in any merged/done/archived task files.
- Searched state branch (oompah/state/proj-14849f1b) tasks: OOMPAH-285–OOMPAH-336 across all status folders. The OOMPAH-318 epic (Add full GitLab forge parity) has children OOMPAH-319–OOMPAH-329. None of these children overlap with OOMPAH-320's scope.
- OOMPAH-319 (recently merged, commit 84985658b): Added forge_kind/forge_base_url project model fields and _validate_forge_config() — project-model configuration work, NOT SCM contract formalization. OOMPAH-319 is the blocker for OOMPAH-320, not a duplicate.
- OOMPAH-321 (open, blocked by OOMPAH-320): 'Complete GitLab Merge Request provider parity' — consumes the contract OOMPAH-320 would define; not a duplicate.
- No task in any state (merged, archived, done, open, in-progress) covers: normalizing CI states as explicit types, structured capability warnings, contract test fixtures against a fake provider, or migrating shared consumers off GitHub-specific methods.

2. Relevant files and evidence:
- oompah/scm.py — SCMProvider (ABC) at line 131, GitHubProvider at line 428, GitLabProvider stub at line 1777. ReviewRequest at line 68 already has ci_status: str, ci_warnings: list[dict], but these are not yet formal typed enums. get_ci_status_for_sha() returns raw strings ('passed'/'failed'/'pending'/''). Several abstract methods lack explicit unavailable-capability semantics.
- plans/gitlab-forge-parity.md — 'Core architecture and interfaces' section is the plan reference; OOMPAH-320 implements exactly this section.
- OOMPAH-319 merge (84985658b) landed on the epic-OOMPAH-318 branch before OOMPAH-320 was dispatched; no SCM contract work was included.

3. Remaining work (for next agent):
- Define CIState enum (passed, failed, pending, unknown) to replace bare strings.
- Define CapabilityWarning or similar structured type for capability-unavailable degradation.
- Add contract-level docstrings documenting error and unavailable-capability semantics on every SCMProvider abstract method.
- Add optional provider methods (get_review_comments, get_review_commits, etc.) with default no-op implementations that degrade gracefully.
- Write contract test fixtures: FakeProvider (minimal pass-through) and run the same suite against GitHubProvider (with HTTP mocks).
- Verify existing review, release, YOLO, churn, and close-gate tests remain green after any type changes.

4. Recommended next focus: refactor (SCMProvider contract formalization + consumer migration + contract tests)
---
author: oompah
created: 2026-07-21 22:58
---
Agent completed successfully in 631s (10341 tokens)
---
author: oompah
created: 2026-07-21 22:58
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 89, Tool calls: 70
- Tokens: 48 in / 10.3K out [10.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 10m 31s
- Log: OOMPAH-320__20260721T224759Z.jsonl
---
author: oompah
created: 2026-07-21 22:58
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 22:58
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 22:58
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-21 23:03
---
Agent completed successfully in 299s (1316575 tokens)
---
author: oompah
created: 2026-07-21 23:03
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 18
- Tokens: 1.3M in / 11.0K out [1.3M total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 59s
- Log: OOMPAH-320__20260721T225838Z.jsonl
---
author: oompah
created: 2026-07-21 23:03
---
Agent completed without closing this issue (299s (1316575 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 23:03
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 23:03
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 23:07
---
Agent completed successfully in 212s (1089407 tokens)
---
author: oompah
created: 2026-07-21 23:07
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 13
- Tokens: 1.1M in / 4.6K out [1.1M total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 32s
- Log: OOMPAH-320__20260721T230355Z.jsonl
---
author: oompah
created: 2026-07-21 23:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:07
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 23:12
---
Understanding: As Test Engineer for OOMPAH-320, reviewing the current state:

The refactoring agent (previous runs) successfully:
1. Added CIStatus enum, CIState alias, CapabilityWarning TypedDict, normalize_ci_status() to oompah/scm.py
2. Added contract tests to tests/test_scm.py (all 173 tests pass)
3. Updated oompah/release_delivery_inventory.py and oompah/release_pick_commit_resolver.py to call get_review_commits() instead of get_pr_commits()
4. Updated tests/test_release_delivery_inventory.py and tests/test_release_pick_commit_resolver.py mocks

However, 16 tests in 5 other test files still mock scm.get_pr_commits but the production code now calls scm.get_review_commits. The fix is to update those test mocks to use get_review_commits.

Affected files:
- tests/test_release_delivery_backlog.py (many mocks)
- tests/test_release_delivery_refresh.py
- tests/test_server_release_addendums.py
- tests/test_server_release_delivery_backlog_factory.py
- tests/test_server_release_delivery_backlog_tracker.py
---
author: oompah
created: 2026-07-21 23:21
---
Implementation complete: Fixed 16 failing test mocks across 5 test files.

Root cause: The refactoring agent correctly updated production code (release_delivery_inventory.py, release_pick_commit_resolver.py) to call scm.get_review_commits() — the forge-neutral contract method — instead of scm.get_pr_commits(). However, 5 test files still mocked scm.get_pr_commits, which on a MagicMock returns a new MagicMock instead of the configured return value when get_review_commits is actually called.

Changes:
- tests/test_release_delivery_backlog.py: Updated 14 mock references
- tests/test_release_delivery_refresh.py: Updated 2 mock references + local function name
- tests/test_server_release_addendums.py: Updated 1 mock reference
- tests/test_server_release_delivery_backlog_factory.py: Updated 4 mock references
- tests/test_server_release_delivery_backlog_tracker.py: Updated 3 mock references

Verification: make test passes — 10525 passed, 36 skipped, 0 failed.
---
author: oompah
created: 2026-07-21 23:22
---
Completion: OOMPAH-320 forge-neutral SCM/CI provider contract is fully delivered.

Delivered in this branch (epic-OOMPAH-318):

1. oompah/scm.py — Contract formalization:
   - CIStatus enum (PASSED, FAILED, PENDING, UNKNOWN) as the canonical CI verdict type
   - CIState alias for forge integrations
   - CapabilityWarning TypedDict for structured capability-unavailable warnings
   - unavailable_capability_warning() helper
   - normalize_ci_status() for legacy string → CIStatus conversion
   - ReviewRequest.__post_init__ normalizes ci_status at the contract boundary
   - SCMProvider ABC with docstrings documenting error/unavailable-capability semantics on every method
   - get_review_commits() as forge-neutral alias bridging to get_pr_commits()
   - get_review_comments() defaults to [] (no exception)
   - get_capability_warnings() reports unsupported optional features
   - get_branch_head_sha() defaults to None
   - get_branch_ci_status() composes head SHA + CI status with UNKNOWN fallback
   - get_ci_status_for_sha() defaults to UNKNOWN

2. Workflow consumers migrated:
   - release_delivery_inventory.py: get_review_commits() instead of get_pr_commits()
   - release_pick_commit_resolver.py: get_review_commits() instead of get_pr_commits()

3. Tests:
   - tests/test_scm.py: 9 new contract tests covering FakeProvider defaults, CI normalization, GitHub provider defaults, and CIState/CIStatus alias
   - 5 additional test files updated so mocks match the get_review_commits contract method
   - make test: 10525 passed, 36 skipped, 0 failed

Acceptance criteria met:
✅ No workflow consumer uses GitHub-specific provider methods for supported behavior
✅ Contract documents error and unavailable-capability semantics in code
✅ make test passes
---
author: oompah
created: 2026-07-21 23:22
---
Forge-neutral SCM/CI provider contract defined and tested. CIStatus enum, CapabilityWarning TypedDict, normalize_ci_status(), get_review_commits() contract method, and SCMProvider docstrings added to oompah/scm.py. 9 new contract tests in test_scm.py. 5 test files updated to mock get_review_commits instead of get_pr_commits. All 10525 tests pass.
---
author: oompah
created: 2026-07-21 23:22
---
Agent completed successfully in 893s (12648 tokens)
---
author: oompah
created: 2026-07-21 23:22
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 90, Tool calls: 61
- Tokens: 52 in / 12.6K out [12.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 14m 53s
- Log: OOMPAH-320__20260721T230734Z.jsonl
---
<!-- COMMENTS:END -->
