---
id: OOMPAH-320
type: task
status: In Progress
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
updated_at: '2026-07-21T22:58:38.415043Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 7bc1c931-8d0a-4bbd-936b-78033bab9102
oompah.task_costs:
  total_input_tokens: 48
  total_output_tokens: 10293
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 48
      output_tokens: 10293
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 48
    output_tokens: 10293
    cost_usd: 0.0
    recorded_at: '2026-07-21T22:58:27.853891+00:00'
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
<!-- COMMENTS:END -->
