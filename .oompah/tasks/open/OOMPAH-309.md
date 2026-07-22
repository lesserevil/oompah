---
id: OOMPAH-309
type: task
status: Open
priority: null
title: Harden shared-epic protection when _resolve_parent_epic fails for a child with
  parent_id set
parent: OOMPAH-307
children:
- OOMPAH-404
blocked_by: []
labels:
- focus-complete:duplicate_detector
- focus-complete:epic_planner
assignee: null
created_at: '2026-07-21T16:53:17.046767Z'
updated_at: '2026-07-22T15:50:48.102473Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 97f521c9-b729-411b-8804-c7b853ca94f6
oompah.task_costs:
  total_input_tokens: 66
  total_output_tokens: 11039
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 66
      output_tokens: 11039
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 39
    output_tokens: 10159
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:34:48.936290+00:00'
  - profile: default
    model: unknown
    input_tokens: 27
    output_tokens: 880
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:42:13.067438+00:00'
---
## Summary

Keep shared-epic protections active when resolving a child parent epic fails.
## Context

The shared-epic protection (no per-task worktree, no per-child PR, no Merged promotion) relies on _resolve_parent_epic(issue) returning a non-None parent Issue. This function calls tracker.fetch_issue_detail(parent_id) and returns None on any error:

- Tracker errors (state branch checkout failure, file not found, decode error)
- Parent task not found in the tracker
- Network/IO errors

When _resolve_parent_epic returns None for a child that HAS a non-empty parent_id, the child falls through to:
1. Per-task worktree creation (line 4808, orchestrator.py)
2. Per-child PR creation (no shared-mode skip in _ensure_review_exists when parent_epic is None)
3. Done→Merged promotion (rollup_strategy is None → skip guard doesn't apply)

This is a latent race condition / transient failure that can cause the OOMPAH-286/PR #466 bug pattern to reappear.

## Implementation scope

1. In _resolve_parent_epic (oompah/orchestrator.py ~line 4651): when fetch_issue_detail raises an exception or returns None but parent_id is non-empty, log a warning and consider returning a sentinel/stub parent rather than None. Alternatively, add a secondary lookup (e.g., check if an epic worktree already exists for parent_id as a proxy signal).

2. In _create_workspace_for_issue: if parent_id is non-empty but _resolve_parent_epic returned None, do NOT fall through to per-task worktree. Instead:
   - Try routing to the epic worktree using the parent_id directly (idempotent call to create_epic_worktree with the parent_id)
   - OR requeue the task (raise a retriable exception) so the next tick retries with a fresh tracker lookup

3. In Done→Merged promotion path (~line 8282): if issue.parent_id is non-empty and rollup_strategy is None (resolution failed), do NOT mark Merged. Log a warning and skip (same as 'shared' behavior).

4. In _ensure_review_exists: if parent_id is non-empty but parent_epic resolution failed, skip per-child PR creation (same as parent_epic not None).

## Relevant files
- oompah/orchestrator.py: _resolve_parent_epic (~line 4651), _create_workspace_for_issue (~line 4719), _ensure_review_exists (~line 7803), Done→Merged promotion (~lines 8280-8330, 8595-8625)

## Tests required
- test_epic_strategy.py: Simulate _resolve_parent_epic raising a tracker error for a child with parent_id; verify _create_workspace_for_issue falls back to epic worktree or requeues (not per-task worktree)
- Verify _ensure_review_exists skips per-child PR when parent_id is set but fetch fails
- Verify Done→Merged promotion does NOT mark child Merged when parent_id is set but rollup_strategy is None

## Acceptance criteria
- A transient tracker error during parent_id resolution does not result in a per-child branch, per-child PR, or premature Merged status
- All checks that gate on rollup_strategy == 'shared' are equally applied when parent_id is set but strategy is undetermined

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:27
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:27
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:27
---
Understanding: Investigating OOMPAH-309 as Duplicate Investigator. The issue is about hardening shared-epic protection when _resolve_parent_epic fails for a child with parent_id set. Will search for similar/duplicate tasks before any implementation work.
---
author: oompah
created: 2026-07-22 05:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:34
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate found. OOMPAH-309 is a unique, unimplemented bug fix.

Candidates reviewed (none are duplicates):
- OOMPAH-219 (Merged): SharedAbsorptionEvidence — covers commit-absorption races on shared branches. Different: that issue is about absorbing uncommitted changes after landing-gate failure; OOMPAH-309 is about what happens when _resolve_parent_epic raises/returns None while the child has parent_id set.
- OOMPAH-165 (Archived): Fix shared epic landed detection before main merge — different: about premature Merged status detection.
- OOMPAH-168 (Archived): Simplify orchestration to shared epic workflow — different: structural dead-code removal.
- OOMPAH-163 (Archived): Allow generated epic target branches through dispatch — different: allowlist bypass for epic branches.
- All .oompah/tasks files (archived, merged, done, open, in-progress, backlog) searched for: resolve_parent_epic, shared_epic, shared-epic protection, parent_id fail, harden, epic protection.

2. Root cause identified in oompah/orchestrator.py:
_resolve_parent_epic() (line 4835) fetches the parent epic from the tracker; any tracker exception causes it to return None. Three places in the code apply shared-epic protection only when parent_epic is not None, so a tracker failure for a child that HAS parent_id set bypasses the protection:

a) _yolo_epic_strategy_block_reason (~line 11929): parent_epic = _resolve_parent_epic(issue); if parent_epic is None: return None — returns no block instead of blocking the stale child task PR.
b) _close_invalid_epic_policy_review (~line 11929 elif branch): elif issue.parent_id and parent_epic is not None: — skips the close logic entirely when resolve fails.
c) Review handoff (~line 8070): if entry.issue.parent_id and parent_epic is not None: skip_per_child_review — fails to skip, creating a per-child PR when it should not.

The fix should: when issue.parent_id is set but _resolve_parent_epic returns None (tracker failure), treat it as if the parent exists for purposes of protection (fail closed), rather than failing open and allowing the child to proceed as standalone work.

3. Remaining work: implement the hardening — the three sites above need guarding. A child with parent_id set and _resolve_parent_epic returning None should block/close/skip the same as when the parent is successfully resolved. Tests needed for all three paths.

4. Recommended next focus: feature (backend fix in oompah/orchestrator.py, covering _yolo_epic_strategy_block_reason, _close_invalid_epic_policy_review, and the review handoff skip)
---
author: oompah
created: 2026-07-22 05:34
---
Agent completed successfully in 215s (10198 tokens)
---
author: oompah
created: 2026-07-22 05:34
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 80, Tool calls: 61
- Tokens: 39 in / 10.2K out [10.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 35s
- Log: OOMPAH-309__20260722T053116Z.jsonl
---
author: oompah
created: 2026-07-22 05:34
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 05:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:36
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-22 05:41
---
Understanding (Epic Planner): This epic covers a targeted hardening fix in oompah/orchestrator.py. Three call sites fail open when _resolve_parent_epic() returns None for an issue that HAS parent_id set (tracker transient error). The previous duplicate-detector agent identified them precisely: (a) _yolo_epic_strategy_block_reason (~line 11855) returns None instead of blocking, (b) _close_invalid_epic_policy_review (~line 11929) skips the close branch, (c) review handoff (~line 8070) creates a per-child PR instead of skipping. All three fixes live in the same file and follow the same pattern: fail closed when parent_id is set. Will decompose into one implementation child (code + tests in one session) since they're tightly coupled and the change is small.
---
author: oompah
created: 2026-07-22 05:42
---
Focus handoff: epic_planner

1. Outcome: Epic decomposed into 1 implementation child task (OOMPAH-404). The scope is intentionally narrow — all three fixes are in the same function group of oompah/orchestrator.py and follow the same pattern (fail-closed when parent_id is set), so one focused feature-agent session covers everything.

2. Relevant files and evidence:
   - oompah/orchestrator.py: _resolve_parent_epic (line 4835), review-handoff skip (line 8070), _yolo_epic_strategy_block_reason (line 11806/11855), _close_invalid_epic_policy_review (line 11868/11929)
   - tests/test_epic_strategy.py: existing patterns for patching _resolve_parent_epic (see TestResolveParentEpic class and TestSharedModeDispatchGating)
   - No existing test covers _yolo_epic_strategy_block_reason or _close_invalid_epic_policy_review directly

3. Remaining work: OOMPAH-404 (the only child) needs a feature agent to implement all three hardening fixes and write the corresponding regression tests.

4. Recommended next focus: feature (backend fix)
---
author: oompah
created: 2026-07-22 05:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 19
- Tokens: 27 in / 880 out [907 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 59s
- Log: OOMPAH-309__20260722T053615Z.jsonl
---
<!-- COMMENTS:END -->
