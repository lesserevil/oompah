---
id: OOMPAH-404
type: task
status: Done
priority: null
title: Harden 3 call sites in orchestrator.py to fail-closed when _resolve_parent_epic
  returns None for a child with parent_id
parent: OOMPAH-309
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-22T05:41:51.997877Z'
updated_at: '2026-07-22T16:13:58.574373Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 8e0a34e5-b6fb-4041-8e00-392fe5ce6ee5
oompah.task_costs:
  total_input_tokens: 1224561
  total_output_tokens: 11527
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1224561
      output_tokens: 11527
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 13
    output_tokens: 3447
    cost_usd: 0.0
    recorded_at: '2026-07-22T15:36:06.392257+00:00'
  - profile: standard
    model: unknown
    input_tokens: 151767
    output_tokens: 1143
    cost_usd: 0.0
    recorded_at: '2026-07-22T15:36:57.638908+00:00'
  - profile: default
    model: unknown
    input_tokens: 1072781
    output_tokens: 6937
    cost_usd: 0.0
    recorded_at: '2026-07-22T15:50:16.163005+00:00'
---
## Summary

### Context

This is the single implementation task for OOMPAH-309. All three problem sites are in oompah/orchestrator.py. The root cause: _resolve_parent_epic() returns None on tracker error AND on 'no parent'. Call sites that guard with \`parent_epic is not None\` fail open — they allow child tasks to proceed as standalone work — when the parent lookup fails transiently while parent_id IS still set on the issue.

### Files to change

- oompah/orchestrator.py (three sites)
- tests/test_epic_strategy.py (new regression tests for all three hardened paths)

### Site 1 — _yolo_epic_strategy_block_reason (~line 11855)

Current code:
\`\`\`python
parent_epic = self._resolve_parent_epic(issue)
if parent_epic is None:
    return None   # <-- BUG: no block, even when parent_id is set
\`\`\`

Fix: when parent_id is set but parent_epic is None, return a block reason indicating the parent could not be resolved and the gate is failing closed. Do NOT return None (which means 'allow').

Suggested fix:
\`\`\`python
parent_epic = self._resolve_parent_epic(issue)
if parent_epic is None:
    if (issue.parent_id or '').strip():
        # Tracker error fetching parent — fail closed rather than allowing
        # a stale child PR through while the parent is temporarily unreachable.
        target_branch = self._review_target_branch(project, review)
        return (
            f'shared epic workflow: child task {issue.identifier} has '
            f'parent {issue.parent_id} but it could not be resolved; '
            f'blocking PR {source_branch}->{target_branch} until '
            'parent epic is reachable'
        )
    return None
\`\`\`

### Site 2 — _close_invalid_epic_policy_review (~line 11929)

Current code:
\`\`\`python
elif (
    issue is not None
    and (issue.parent_id or '').strip()
):
    parent_epic = self._resolve_parent_epic(issue)
    if parent_epic is not None:   # <-- BUG: skips close when resolve fails
        ...
\`\`\`

Fix: the elif body that resolves and closes should also handle the parent_epic is None + parent_id is set case. When parent_id is set but parent_epic is None (tracker error), we cannot safely determine whether to close, so we should NOT close (closing is destructive). The block reason from Site 1 already blocks the merge. So the fix here is to add a log entry and return False when parent_epic is None and parent_id is set, rather than silently skipping. Adjust the condition to handle both branches explicitly.

Note: there is a nuance here — do NOT close the PR in this case (a transient failure shouldn't permanently close a valid PR). The block from Site 1 is enough. Just make sure the code path explicitly handles the None-but-parent_id-set case, and logs it, rather than falling through to close_comment being empty and returning False silently.

### Site 3 — review handoff per-child skip (~line 8070)

Current code:
\`\`\`python
parent_epic: Issue | None = None
if entry.issue and entry.issue.parent_id:
    parent_epic = self._resolve_parent_epic(entry.issue)

if (
    entry.issue is not None
    and (entry.issue.parent_id or '').strip()
    and parent_epic is not None   # <-- BUG: skips protection when resolve fails
):
    # skip per-child review
    return True
\`\`\`

Fix: when parent_id is set, skip the per-child review regardless of whether parent_epic resolved. A child with a parent_id set should never get its own standalone PR — even when the parent lookup fails. Change \`and parent_epic is not None\` to just check parent_id.

\`\`\`python
if (
    entry.issue is not None
    and (entry.issue.parent_id or '').strip()
):
    # Skip per-child review: this issue belongs to a parent epic.
    # We protect even when _resolve_parent_epic fails (tracker error) because
    # a child with parent_id set must never land as a standalone task PR.
    logger.debug(
        'Skip per-child review for %s: child has parent %s (epic=%s)',
        entry.identifier,
        entry.issue.parent_id,
        parent_epic.identifier if parent_epic else 'unresolved',
    )
    return True
\`\`\`

### Tests required (tests/test_epic_strategy.py)

Add three tests (one per site), all exercising the scenario:
- issue.parent_id is set (non-empty)
- _resolve_parent_epic returns None (simulate tracker error via patch)

Test names:
1. test_yolo_epic_strategy_blocks_when_parent_id_set_but_resolve_fails
   — assert _yolo_epic_strategy_block_reason returns a non-None string mentioning 'could not be resolved'
2. test_close_invalid_epic_policy_review_does_not_close_when_parent_resolve_fails
   — assert _close_invalid_epic_policy_review returns False (does not close) when parent_id set but parent_epic is None (tracker error)
3. test_review_handoff_skips_per_child_review_when_parent_id_set_but_resolve_fails
   — assert the skip-per-child-review condition returns True when parent_id is set and parent_epic is None

### Acceptance criteria

- All three test cases pass
- make test passes (no regressions)
- A child PR with parent_id set but tracker failure never proceeds as standalone work
- Code comments explain the fail-closed rationale at each site

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 15:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 15:34
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 15:35
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate found. OOMPAH-404 is a fresh, legitimate implementation task.

Candidates reviewed:
- OOMPAH-309 (In Progress, parent): This is the parent epic of OOMPAH-404 — not a duplicate. OOMPAH-404 was explicitly created by the epic_planner agent on OOMPAH-309 as the sole implementation child.
- OOMPAH-281 (Open): Self-hosted GitHub Actions runner — completely unrelated.
- OOMPAH-282 (Backlog): UnicodeEncodeError in state_branch_migration — completely unrelated.
- OOMPAH-235 (Done): Tracker write recovery — completely unrelated.
- Full .oompah/tasks/ tree searched (archived, done, merged, open, backlog) with rg patterns: resolve_parent_epic, fail-closed, parent_id, yolo_epic_strategy, close_invalid_epic, harden. Zero matches outside OOMPAH-309 and OOMPAH-404 itself.

2. Relevant files and evidence from prior OOMPAH-309 agents:
- oompah/orchestrator.py: three bug sites at ~line 8070, ~line 11855, ~line 11929
- tests/test_epic_strategy.py: existing test patterns for _resolve_parent_epic
- The description contains exact line numbers, current buggy code, and suggested replacement code for all three sites.

3. Remaining work: Full implementation — three code changes in oompah/orchestrator.py and three new tests in tests/test_epic_strategy.py (exact test names specified in the description).

4. Recommended next focus: feature (backend implementation)
---
author: oompah
created: 2026-07-22 15:36
---
Agent completed successfully in 94s (3460 tokens)
---
author: oompah
created: 2026-07-22 15:36
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 25, Tool calls: 17
- Tokens: 13 in / 3.4K out [3.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 34s
- Log: OOMPAH-404__20260722T153434Z.jsonl
---
author: oompah
created: 2026-07-22 15:36
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 15:36
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 15:36
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-22 15:36
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 3
- Tokens: 151.8K in / 1.1K out [152.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 34s
- Log: OOMPAH-404__20260722T153625Z.jsonl
---
author: oompah
created: 2026-07-22 15:36
---
Agent completed successfully in 34s (152910 tokens)
---
author: oompah
created: 2026-07-22 15:37
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-309`. Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 15:37
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-22 15:37
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-22 15:44
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 15:44
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-22 15:50
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 20
- Tokens: 1.1M in / 6.9K out [1.1M total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 57s
- Log: OOMPAH-404__20260722T154420Z.jsonl
---
author: oompah
created: 2026-07-22 15:50
---
Agent completed successfully in 357s (1079718 tokens)
---
author: oompah
created: 2026-07-22 15:50
---
Agent completed without closing this issue (357s (1079718 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 15:50
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 15:50
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-22 16:07
---
Discovery: The OOMPAH-404 code changes are already committed (d3d733989) but caused 10 test regressions. Root cause: existing tests use raw MagicMock() for issue objects without setting parent_id=None. The new fail-closed code in _yolo_epic_strategy_block_reason sees a truthy MagicMock as a set parent_id and blocks those PRs. Fix: update 10 tests across 3 files to explicitly set parent_id=None or fetch_issue_detail.return_value=None.
---
author: oompah
created: 2026-07-22 16:13
---
Implementation complete. All changes pushed.

Summary of work done:

1. Site 1 (_yolo_epic_strategy_block_reason, ~line 11908): When parent_id is set but _resolve_parent_epic returns None, now returns a block reason string instead of None. Previously failed open (allowed merge); now fails closed.

2. Site 2 (_close_invalid_epic_policy_review, ~line 11990): When parent_id is set but parent_epic is None (tracker error), now logs a WARNING and returns False instead of silently skipping. A transient failure must not destructively close a valid child PR.

3. Site 3 (review handoff per-child skip, ~line 8069): Removed 'and parent_epic is not None' guard. A child with parent_id set must never get a standalone PR, even when the parent lookup fails transiently.

Tests added in tests/test_epic_strategy.py:
- TestYoloEpicPolicyFailClosed::test_yolo_epic_strategy_blocks_when_parent_id_set_but_resolve_fails
- TestYoloEpicPolicyFailClosed::test_close_invalid_epic_policy_review_does_not_close_when_parent_resolve_fails
- TestEnsureReviewExistsRespectsEpicStrategy::test_review_handoff_skips_per_child_review_when_parent_id_set_but_resolve_fails

Additional fix: 10 pre-existing tests in test_orchestrator_merged.py, test_yolo_watchdog.py, test_yolo_watchdog_w9m.py used raw MagicMock() without parent_id=None, causing them to trip the new fail-closed gate. Fixed by explicitly setting parent_id=None or fetch_issue_detail.return_value=None.

Full suite: 11709 passed, 38 skipped, 0 failures.
---
author: oompah
created: 2026-07-22 16:13
---
Hardened 3 call sites in orchestrator.py to fail-closed when _resolve_parent_epic returns None for a child with parent_id. Added 3 regression tests. Fixed 10 test regressions caused by MagicMock parent_id attributes. All 11709 tests pass.
---
<!-- COMMENTS:END -->
