---
id: OOMPAH-311
type: task
status: In Progress
priority: null
title: Diagnose and surface remediation path for existing independently-merged child
  branches/PRs
parent: OOMPAH-307
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T16:53:58.500869Z'
updated_at: '2026-07-22T05:46:11.706985Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: b37306bb-a3cb-4206-af15-9c085e2c6c7e
oompah.task_costs:
  total_input_tokens: 308560
  total_output_tokens: 9427
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 308560
      output_tokens: 9427
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 308540
    output_tokens: 2019
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:30:23.701705+00:00'
  - profile: default
    model: unknown
    input_tokens: 20
    output_tokens: 7408
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:45:56.863923+00:00'
---
## Summary

Diagnose and provide remediation for independently merged shared-epic child branches and PRs.
## Context

OOMPAH-286 was a child of epic OOMPAH-285 but received its own branch (OOMPAH-286) and PR #466 which merged to main. This is the exact bug OOMPAH-307 wants to prevent. The existing data cannot be reverted (history preserved), but the system should:
1. Detect that a shared-epic child has an independently-merged PR to main (not to the epic branch)
2. Surface a clear operator message without corrupting the epic branch or rewriting history
3. Ensure the detection path is safe and non-destructive

## Implementation scope

1. Add a diagnostic scan in the orchestrator reconciliation loop (or in _epic_auto_close_check / _open_epic_main_prs) that detects shared-epic children whose work_branch (or branch_name) was merged directly to the project's default_branch (not the parent epic branch).

2. When detected, add a tracker comment on the affected child with:
   - 'Detected independent branch merge: branch <X> was merged to <default_branch> via PR #<N> instead of through the parent epic <Y> on branch epic-<Y>. Commits are preserved in <default_branch>. The parent epic OOMPAH-285 branch may not contain these commits. Operator action: cherry-pick <branch> commits to epic-<Y> if missing, then close PR or mark this task as reconciled.'
   - Log the diagnostic at WARNING level

3. Add a tracker label (e.g., needs:reconcile) to the affected child and do NOT promote it to Merged (it's already been merged independently so standard Merged promotion is confusing).

4. Ensure the parent epic's _epic_auto_close_check treats independently-merged children as 'merged_summaries' (already-handled, per the existing 'merged directly to {target_branch}' branch at line 4932) so the epic is not permanently stuck.

5. Ensure the implementation does NOT modify git history, force-push, or close/reopen PRs that are already merged.

## Relevant files
- oompah/orchestrator.py: _epic_auto_close_check (~line 4877+), _open_epic_main_prs (~line 5349), existing 'merged directly to target_branch' handling at ~line 4932

## Tests required
- Test that a shared-epic child whose branch is in merged_branches (to default_branch, not epic branch) triggers the diagnostic comment
- Test that the diagnostic does not crash when the child PR is already closed/merged
- Test that the parent epic is not stuck (the independently-merged child is treated as reconciled for epic completion purposes)
- Fixture mimicking the OOMPAH-286/PR #466 scenario: child.branch_name='OOMPAH-286', PR merged to main; verify diagnostic is posted and epic is not permanently blocked

## Acceptance criteria
- Existing independently-merged children are detected and surfaced to operators with actionable remediation instructions
- No git history is rewritten; commits are preserved
- The parent epic is not permanently stuck due to the misrouted child
- A dedicated test fixture prevents regression of the OOMPAH-285/286 routing outcome

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:29
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:29
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:30
---
Agent completed successfully in 52s (310559 tokens)
---
author: oompah
created: 2026-07-22 05:30
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 308.5K in / 2.0K out [310.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 52s
- Log: OOMPAH-311__20260722T052934Z.jsonl
---
author: oompah
created: 2026-07-22 05:30
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-307`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 05:30
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 05:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:45
---
Understanding: I am a Duplicate Investigator for OOMPAH-311 ('Diagnose and surface remediation path for existing independently-merged child branches/PRs'). This task is a child of epic OOMPAH-307. My job is to confirm whether this task is a duplicate of any existing issue before any implementation begins. I will search the task store for any prior work covering diagnosis/remediation of independently-merged shared-epic child branches.
---
author: oompah
created: 2026-07-22 05:45
---
Discovery: Duplicate screening found NO duplicate for OOMPAH-311.

Search scope: all .oompah/tasks/ folders (archived, merged, done, open, in-progress, backlog), plans/, docs/, README.md, WORKFLOW.md.

Keywords searched: 'independently merged', 'child branch remediation', 'epic child', 'OOMPAH-286 pattern', 'diagnose.*branch', 'surface.*remediat', 'existing.*merged child'.

Closest candidates reviewed and REJECTED as duplicates:
- OOMPAH-308 (Needs Human): Fix stale work_branch metadata — different; covers routing-time metadata correction, not diagnosis of already-merged children.
- OOMPAH-309 (Backlog): Harden _resolve_parent_epic failure path — different; covers runtime protection hardening, not historical data reconciliation.
- OOMPAH-310 (Open): Verify Merged promotion lifecycle — different; covers status promotion gating, not existing independently-merged child data.
- OOMPAH-312 (Open): UI/dashboard status display — different; covers display labels, not remediation.
- OOMPAH-313 (Open): Regression tests — different; covers test coverage, not operator remediation tooling.
- OOMPAH-165 (Archived): Shared epic landed detection before main merge — different topic.
- OOMPAH-219 (Archived): SharedAbsorptionEvidence commit-absorption races — different topic.

Conclusion: OOMPAH-311 is unique. It addresses Gap E from the OOMPAH-307 epic planner analysis: no code path currently detects or reports on children that were already independently merged to main (OOMPAH-286/PR #466 pattern), and no operator remediation path exists for that historical state.
---
author: oompah
created: 2026-07-22 05:45
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate found. OOMPAH-311 is a unique, unimplemented task covering Gap E from epic OOMPAH-307: detecting and surfacing a remediation path for existing shared-epic children that were already independently merged to main (the OOMPAH-286/PR #466 pattern).

2. Evidence and context from epic planner (OOMPAH-307 comment #15):
   - Gap E: No code path updates or detects children that already independently merged. Children like OOMPAH-286 received work_branch=OOMPAH-286, target_branch=main, PR #466, and status Merged — bypassing the epic branch entirely.
   - Key files to modify: oompah/orchestrator.py (startup reconciliation or a new diagnostic path), oompah/models.py (possibly new field for 'diagnosed_independent_merge'), oompah/oompah_md_tracker.py (for native tracker data reads).
   - Related sibling tasks: OOMPAH-308 (stale metadata fix), OOMPAH-309 (protection hardening), OOMPAH-310 (promotion lifecycle). OOMPAH-311 is independent and can proceed in parallel.

3. Implementation scope (from OOMPAH-307 description):
   - Detect independently-created child PRs/branches by scanning children of shared epics for work_branch != parent_epic.work_branch and status==Merged/pr_url pointing to main.
   - Surface diagnostics: either a CLI command, operator log message, or dashboard indicator that lists affected children and their independent merge evidence.
   - Provide a safe remediation path: e.g., re-associate the child's commits to the epic branch, update metadata, or annotate the child as 'independently-merged (no action needed if commits are in main)'. Do NOT rewrite git history.
   - Tests: detection of OOMPAH-286-style children, diagnostic output format, remediation path execution, no corruption of epic branch on reconcile.
   - Acceptance: existing independently-merged child data is diagnosed and does NOT corrupt the epic branch.

4. Remaining work: Full implementation. No code has been written yet.

5. Recommended next focus: feature (implement diagnosis and remediation tooling in oompah/orchestrator.py).
---
author: oompah
created: 2026-07-22 05:45
---
Agent completed successfully in 170s (7428 tokens)
---
author: oompah
created: 2026-07-22 05:45
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 42, Tool calls: 28
- Tokens: 20 in / 7.4K out [7.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 50s
- Log: OOMPAH-311__20260722T054311Z.jsonl
---
author: oompah
created: 2026-07-22 05:46
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 05:46
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 05:46
---
Focus: Epic Planner
---
<!-- COMMENTS:END -->
