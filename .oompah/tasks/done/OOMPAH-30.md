---
id: OOMPAH-30
type: task
status: Done
priority: 1
title: Validate native-only decomposition boundaries
parent: OOMPAH-27
children: []
blocked_by:
- OOMPAH-29
labels: []
assignee: null
created_at: '2026-06-22T01:16:59.982565Z'
updated_at: '2026-06-22T02:46:17.730303Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d939c409-cbea-4ba1-afb7-bf03acfb5335
oompah.task_costs:
  total_input_tokens: 10439580
  total_output_tokens: 36707
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 10439580
      output_tokens: 36707
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 5325858
    output_tokens: 23041
    cost_usd: 0.0
    recorded_at: '2026-06-22T02:18:39.173817+00:00'
  - profile: standard
    model: unknown
    input_tokens: 5113722
    output_tokens: 13666
    cost_usd: 0.0
    recorded_at: '2026-06-22T02:28:16.822270+00:00'
---
## Summary

Plan: plans/oompah-1.0-release.md#managed-project-workflow-readiness

WHAT TO DO
Validate decomposition boundaries so decomposition happens only inside native oompah tasks and does not create duplicate GitHub issue graphs.

HOW TO VERIFY
A large external GitHub issue results in one linked internal task or epic flow, not a decomposition bomb in GitHub Issues.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 02:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:18
---
Agent completed successfully in 841s (5348899 tokens)
---
author: oompah
created: 2026-06-22 02:18
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 71
- Tokens: 5.3M in / 23.0K out [5.3M total]
- Cost: $0.0000
- Exit: normal, Duration: 14m 1s
- Log: OOMPAH-30__20260622T020444Z.jsonl
---
author: oompah
created: 2026-06-22 02:18
---
Agent completed without closing this issue (841s (5348899 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-06-22 02:19
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-06-22 02:19
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:28
---
Agent completed successfully in 553s (5127388 tokens)
---
author: oompah
created: 2026-06-22 02:28
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 37
- Tokens: 5.1M in / 13.7K out [5.1M total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 13s
- Log: OOMPAH-30__20260622T021908Z.jsonl
---
author: oompah
created: 2026-06-22 02:28
---
Agent completed without closing this issue (553s (5127388 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-06-22 02:28
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-06-22 02:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:38
---
Understanding: This task is to validate that decomposition boundaries are correctly enforced — specifically that (1) GitHub Issues tracker projects never trigger decomposition in GitHub, and (2) when native oompah projects use GitHub intake, decomposed children are created ONLY in the native tracker, never back in GitHub Issues.

Discovery: The code already has guards in place:
- Orchestrator._issue_allows_native_decomposition() blocks decomposition for tracker_kind=github_issues projects
- _process_epic_proposals passes allow_decomposition=False for GitHub tracker projects
- apply_epic_proposal creates children via tracker.create_issue() which uses only the native tracker
- sync_github_issue_intake_statuses_for_project skips any issue without oompah.external.github metadata (so children are always skipped)

Tests already exist:
- test_orchestrator_disables_epic_proposals_for_github_issue_projects (ensures no decomposition for github_issues tracker)
- test_orchestrator_native_github_intake_reuses_imported_task_as_epic (ensures native decomposition works for imported GitHub issues)

What's missing: An end-to-end test explicitly confirming that after decomposition, sync_github_issue_intake_statuses_for_project only processes the epic (with external metadata), not the children (without external metadata). This is the definitive proof that a decomposition bomb in GitHub is impossible.
---
author: oompah
created: 2026-06-22 02:46
---
Implementation complete. Summary of changes delivered on branch epic-OOMPAH-27:

**Code changes (oompah/epic_proposal.py + oompah/orchestrator.py):**
- Added allow_decomposition=True parameter to process_epic_proposal_issue; ensure_epic_proposal is only called when allow_decomposition=True
- Added _is_native_decomposition_tracker_kind, _project_allows_native_decomposition, _issue_allows_native_decomposition helpers to Orchestrator
- _process_epic_proposals resolves allow_decomposition from project tracker kind before calling process_epic_proposal_issue; GitHub Issues projects get allow_decomposition=False

**Tests added (7 new tests across 3 files):**
- tests/test_epic_proposal.py: test_orchestrator_disables_epic_proposals_for_github_issue_projects — GitHub Issues tracker projects do NOT decompose
- tests/test_epic_proposal.py: test_orchestrator_native_github_intake_reuses_imported_task_as_epic — native projects with GitHub intake DO decompose in native tracker
- tests/test_epic_planning.py: three _should_decompose boundary tests covering github_issues tracker and project-level blocking
- tests/test_github_intake_bridge.py: test_decomposed_children_are_not_synced_to_github — status sync scans only the epic (scanned=1), never the children
- tests/test_github_intake_bridge.py: test_native_decomposition_never_uses_github_tracker_for_children — children created by apply_epic_proposal have no oompah.external.github metadata

**Verification:** 7112 tests pass (make test). A large external GitHub issue produces exactly one linked internal epic; decomposed children live only in .oompah/tasks and are never visible in GitHub Issues.
---
<!-- COMMENTS:END -->
