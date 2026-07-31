---
id: OOMPAH-428
type: task
status: Needs Human
priority: null
title: Harden PR creation gate and work_branch reconciliation for shared-epic child
  tasks
parent: OOMPAH-426
children: []
blocked_by:
- OOMPAH-427
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-23T21:34:08.303204Z'
updated_at: '2026-07-31T06:00:14.504029Z'
work_branch: epic-OOMPAH-426
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: ba072b55-6de2-46c2-9a35-95a735117575
oompah.work_branch: epic-OOMPAH-426
oompah.task_costs:
  total_input_tokens: 727405
  total_output_tokens: 12884
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 727405
      output_tokens: 12884
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 727357
    output_tokens: 3197
    cost_usd: 0.0
    recorded_at: '2026-07-23T22:12:35.974614+00:00'
  - profile: standard
    model: unknown
    input_tokens: 22
    output_tokens: 8994
    cost_usd: 0.0
    recorded_at: '2026-07-23T22:16:20.611107+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 26
    output_tokens: 693
    cost_usd: 0.0
    recorded_at: '2026-07-30T22:37:21.232531+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-1d3214571ebe
    project_id: proj-14849f1b
    task_id: OOMPAH-428
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0223e6cbfdd490bec9b7f1a26f82dc0aa9419f1f40da91657544383f40767732
    attempts:
    - version: 1
      attempt_id: attempt-e6b946c713cc
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0223e6cbfdd490bec9b7f1a26f82dc0aa9419f1f40da91657544383f40767732
      created_at: '2026-07-30T22:36:12.130565+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T22:36:12.130565+00:00'
      branch_key: epic-OOMPAH-426
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-07-30T22:31:38.986991+00:00'
    updated_at: '2026-07-30T22:36:12.130565+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-e6b946c713cc
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0223e6cbfdd490bec9b7f1a26f82dc0aa9419f1f40da91657544383f40767732
    created_at: '2026-07-30T22:36:12.130565+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T22:36:12.130565+00:00'
    branch_key: epic-OOMPAH-426
---
## Summary

### Context

This is the defense-in-depth companion to OOMPAH-427 (YOLO gate fix). While OOMPAH-427 patches the merge-time gate, this task audits and hardens the earlier gates: PR creation (\`_ensure_review_exists\`) and branch/work_branch reconciliation (\`_create_workspace_for_issue\`).

OOMPAH-427 must be merged before this task starts.

### Scope

### 1. Audit \`_ensure_review_exists\` (~line 8138 of \`oompah/orchestrator.py\`)

Current logic blocks per-child PR creation via:
\`\`\`python
if (entry.issue is not None and (entry.issue.parent_id or '').strip()):
    return True  # no per-child PR
\`\`\`

Potential gap: if \`entry.issue.parent_id\` is absent due to a partial load or tracker error, the function falls through and may create a per-child PR. Harden this path:
- If \`entry.issue\` has no parent_id but the parent CAN be resolved (via \`_resolve_parent_epic\` or tracker lookup), block PR creation and fail closed
- Add a diagnostic log line when blocking due to resolved parent

### 2. Audit \`_create_workspace_for_issue\` (~line 5001 of \`oompah/orchestrator.py\`)

The function corrects stale \`work_branch\` on the child before routing to the epic worktree:
\`\`\`python
if current_child_branch != epic_branch:
    issue.work_branch = epic_branch
    issue.branch_name = epic_branch
    tracker.set_metadata_field(issue.identifier, 'oompah.work_branch', epic_branch)
\`\`\`

Edge case: the \`set_metadata_field\` call may fail silently (TrackerError is caught and logged). If the correction is NOT persisted, subsequent orchestrator restarts see the stale work_branch again, which is what EXOCOMP-57 exploited. This is already the current behavior, but verify the in-memory correction is always applied even when the tracker write fails. No change required if it is.

### 3. Work_branch override path in reconciliation

The reconciliation path (\`_reconcile_independently_merged_children\`) detects children that bypassed the epic branch AFTER the fact (MERGED state). Verify it correctly labels the EXOCOMP-57 scenario (\`child.work_branch = 'EXOCOMP-57'\`, child state = MERGED, parent epic open or merged, epic_branch = 'epic-EXOCOMP-9'). Add a regression test if it doesn't already cover this.

### Tests required (in \`tests/test_epic_strategy.py\`)

Add to the existing \`TestEnsureReviewExists\` class (around line 1170):
- \`test_shared_child_pr_blocked_even_with_stale_own_work_branch\`: entry.issue has \`parent_id\` set AND \`work_branch\` equal to the child's own identifier (not the epic branch). \`_ensure_review_exists\` must return True without creating a PR.
- \`test_shared_child_pr_blocked_when_parent_id_missing_but_parent_resolvable\` (if the hardening above is implemented): entry.issue.parent_id is None/empty but tracker returns a parent epic. Must block PR creation.

Add/verify in reconciliation tests:
- \`test_detects_independently_merged_child_with_stale_own_work_branch\`: child.work_branch='child-id', epic_branch='epic-parent-id', child state=MERGED → \`_detect_independently_merged_children\` must flag this child.

### Acceptance criteria

1. \`_ensure_review_exists\` never creates a per-child PR when \`issue.parent_id\` is set, regardless of \`work_branch\` value
2. \`_create_workspace_for_issue\` always corrects the child's in-memory \`work_branch\` to the epic branch before routing, even when tracker persistence fails
3. \`_detect_independently_merged_children\` / \`_reconcile_independently_merged_children\` labels the EXOCOMP-57 pattern correctly
4. All existing epic strategy tests still pass
5. \`make test\` passes

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 22:10
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 22:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 22:12
---
Agent completed successfully in 104s (730554 tokens)
---
author: oompah
created: 2026-07-23 22:12
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 9
- Tokens: 727.4K in / 3.2K out [730.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 44s
- Log: OOMPAH-428__20260723T221057Z.jsonl
---
author: oompah
created: 2026-07-23 22:12
---
Agent completed without closing this issue (104s (730554 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-23 22:12
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-23 22:12
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 22:16
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-428 is a unique, confirmed task with distinct scope from all prior work.

**Duplicate screening performed:**
Searched all .oompah/tasks/ files, git log, and tests/ for: ensure_review_exists, _create_workspace_for_issue, reconcile_independently, detect_independently_merged, work_branch reconciliation, PR creation gate, harden PR, defense-in-depth, shared-epic child PR, EXOCOMP-57.

**Closest candidates reviewed and ruled out:**

1. **OOMPAH-308** (merged commit 1e52f6134): 'Fix stale work_branch metadata for shared-epic children on dispatch' — Implements the work_branch correction in _create_workspace_for_issue. OOMPAH-428 scope 2 asks to VERIFY the in-memory correction is applied even when tracker write fails. Looking at the code (oompah/orchestrator.py ~line 5024-5040), the in-memory correction (issue.work_branch = epic_branch, issue.branch_name = epic_branch) is applied BEFORE the try block, so this acceptance criterion is already satisfied — no code change needed.

2. **OOMPAH-427** (Done): Fixed _yolo_epic_strategy_block_reason and _close_invalid_epic_policy_review. OOMPAH-428 is about DIFFERENT functions (_ensure_review_exists, _detect_independently_merged_children) — complementary defense-in-depth.

3. **OOMPAH-309** (merged via epic-OOMPAH-309 commit 8b4521d29): Hardened fail-closed when _resolve_parent_epic returns None for a child WITH parent_id set. OOMPAH-428 scope 1 is about a DIFFERENT gap: parent_id absent but parent RESOLVABLE.

4. **OOMPAH-413** (commit 4e0fe8c07): Added tests for _label_merged_issues and _reconcile_merged_epic_children. OOMPAH-428 needs tests for _ensure_review_exists and _detect_independently_merged_children — different functions.

**Key code review findings:**

1. _ensure_review_exists (orchestrator.py ~8138): The gate at lines 8170-8186 checks only (entry.issue.parent_id or '').strip(). The parent_epic is already resolved (line 8171) before the check. Hardening gap: if parent_id is absent/empty but parent_epic is non-None (resolved via tracker lookup), the function falls through and may create a per-child PR. Fix: also block when parent_epic is not None.

2. _create_workspace_for_issue (orchestrator.py ~4973): The in-memory correction (issue.work_branch = epic_branch) happens BEFORE the try/except block around set_metadata_field. Acceptance criterion 2 is ALREADY satisfied — no code change required, just a verification test (optional).

3. _detect_independently_merged_children (orchestrator.py ~10617): Already handles the EXOCOMP-57 pattern correctly: checks child.work_branch != epic_branch and child state == MERGED. Existing tests in tests/test_independently_merged.py cover this logic generically.

**Tests that exist (TestEnsureReviewExistsRespectsEpicStrategy ~line 1202):**
- test_require_epic_parent_blocks_top_level_task_review ✓
- test_require_epic_parent_blocks_unresolved_parent_review ✓
- test_flat_creates_pr_targeting_main ✓
- (no test for: shared child with parent_id set + stale own work_branch)
- (no test for: parent_id absent but parent resolvable)

**Tests that exist (tests/test_independently_merged.py):**
- test_detects_child_with_own_branch_merged_to_main ✓ (generic version)
- (no test with exact EXOCOMP-57 scenario naming as required by OOMPAH-428)

**Implementation required:**
1. Harden _ensure_review_exists: add 'or parent_epic is not None' to the child-block condition (~line 8178), with a debug log showing which condition triggered
2. Add 3 new tests:
   - test_shared_child_pr_blocked_even_with_stale_own_work_branch (in TestEnsureReviewExistsRespectsEpicStrategy)
   - test_shared_child_pr_blocked_when_parent_id_missing_but_parent_resolvable (in TestEnsureReviewExistsRespectsEpicStrategy)  
   - test_detects_independently_merged_child_with_stale_own_work_branch (in test_independently_merged.py or test_epic_strategy.py)
3. _create_workspace_for_issue: NO code change (already correct), optional verification test

**Recommended next focus:** feature (bug fix / hardening implementation)
---
author: oompah
created: 2026-07-23 22:16
---
Agent completed successfully in 204s (9016 tokens)
---
author: oompah
created: 2026-07-23 22:16
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 51, Tool calls: 33
- Tokens: 22 in / 9.0K out [9.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 24s
- Log: OOMPAH-428__20260723T221258Z.jsonl
---
author: oompah
created: 2026-07-23 22:16
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-23 22:16
---
YOLO: merged PR #544.
---
author: oompah
created: 2026-07-30 22:31
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-07-30 22:36
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 22:36
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 22:37
---
The parent epic OOMPAH-426 merged from epic-OOMPAH-426, but this task was In Validation with work branch epic-OOMPAH-426. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-30 22:37
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 13
- Tokens: 26 in / 693 out [719 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 8s
- Log: OOMPAH-428__20260730T223622Z.jsonl
---
author: oompah
created: 2026-07-30 22:39
---
The parent epic OOMPAH-426 merged from epic-OOMPAH-426, but this task was Needs Human with work branch epic-OOMPAH-426. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-31 06:00
---
Post-restart re-evaluation: prerequisite OOMPAH-427 landed in PR #544, but OOMPAH-428 pre-PR and reconciliation hardening was not implemented. Remaining accepted work is now tracked actionably in top-level OOMPAH-641 because this child belongs to an already-merged epic. Archiving this stale child as superseded, not as fully completed.
---
<!-- COMMENTS:END -->
