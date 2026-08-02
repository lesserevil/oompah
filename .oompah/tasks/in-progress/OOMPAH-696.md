---
id: OOMPAH-696
type: bug
status: In Progress
priority: 1
title: Honor integrated SHA evidence after epic child branches are pruned
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T16:18:38.337420Z'
updated_at: '2026-08-02T16:31:08.347758Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: afb70785550116c116dcb05d7957a4ee7909f9aac7e504fe0803f21f99c7e48f
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-02T16:24:20.395564+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Active tasks OOMPAH-281 and OOMPAH-282 are unrelated. Closest historical
    tasks OOMPAH-162 and OOMPAH-219 are Archived and cover different landing scenarios,
    so they are excluded as duplicate targets.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: f2bcb30e-1b03-459d-ae56-0dace58463a7
oompah.task_costs:
  total_input_tokens: 356919
  total_output_tokens: 1867
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 356919
      output_tokens: 1867
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 356919
    output_tokens: 1867
    cost_usd: 0.0
    recorded_at: '2026-08-02T16:24:20.393623+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-696__20260802T162333Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-696
    source_sha: b7fdf2b3f6dfa00f39659abafb176f3d67579dce
    completed_at: '2026-08-02T16:24:20.407899+00:00'
---
## Summary

Triggered by: OOMPAH-691

After epic OOMPAH-691 merged to main, OOMPAH-692 through OOMPAH-695 were moved from audited Done to Needs Human even though every integration.integrated_sha is an ancestor of origin/main. The post-merge child reconciler refreshes missing private branch refs, then _child_landing_evidence_block_reason fails closed solely because child.work_branch differs from the epic branch and the already-landed private branch has been pruned. It ignores the durable integration record, causing a Needs Human/reopen/re-escalate loop and misleading missing-work instructions.

Implementation scope:
- In merged-epic child reconciliation, treat a persisted integration record in state integrated with integrated_sha/head_sha reachable from the authoritative epic container or landed target branch as affirmative landing evidence.
- Check durable commit evidence before requiring a live child branch ref; branch cleanup after successful integration must not invalidate completed work.
- Preserve fail-closed behavior when the recorded SHA is absent, unreachable, or cannot be checked because authoritative target refs are stale/unavailable.
- Keep incomplete Open/In Progress/repair-state children visible and do not promote genuinely stranded commits.
- Suppress repeated Needs Human/watchdog churn once landing is proven, and allow the normal coordinator path to mark the child Merged.
- Review cleanup ordering so integration evidence remains usable after local/remote worktree and branch pruning.

Relevant code: oompah/orchestrator.py _mark_epic_merged, _child_landing_evidence_block_reason, candidate-ref refresh/cleanup helpers, integration queue metadata, and tests/test_epic_strategy.py.

Required tests:
- A Done child with a pruned private branch and integrated_sha contained in the merged epic/main target is promoted rather than moved to Needs Human.
- The exact OOMPAH-692..695 pattern remains idempotently terminal across repeated reconciliation/watchdog passes.
- An integrated_sha not reachable from the container still yields actionable Needs Human recovery instructions.
- Authoritative fetch/transport failure defers reconciliation without asserting success or missing work.
- An incomplete child and a child with genuinely unlanded commits remain non-terminal.

Acceptance criteria:
- Successful branch pruning cannot erase durable landing proof.
- No completed epic child cycles Done -> Needs Human -> Open -> Needs Human solely because its private branch was deleted.
- Existing stranded-work safety tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 16:23
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 16:23
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 16:24
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 6
- Tokens: 356.9K in / 1.9K out [358.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 53s
- Log: OOMPAH-696__20260802T162333Z.jsonl
---
author: oompah
created: 2026-08-02 16:24
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-02 16:24
---
Focus: Callback Auth Validation Specialist
---
author: oompah
created: 2026-08-02 16:24
---
Understanding: This bug occurs when an epic's child tasks have been integrated (their commits are in main), but their private branches have been pruned. The reconciliation logic fails to recognize successful integration and incorrectly moves Done children to Needs Human. I need to fix _child_landing_evidence_block_reason and related logic in orchestrator.py to check durable integration records (integrated_sha) before requiring live branch refs. The fix must preserve fail-closed behavior when SHAs are unreachable but suppress churn when landing is proven.
---
author: oompah
created: 2026-08-02 16:26
---
Discovery: Found the root cause in _mark_epic_merged (line 18671). When a Done child's private branch is pruned, _child_landing_evidence_block_reason fails closed because the branch refs no longer exist. However, there's an integration record (accessible via child.integration) that shows integrated_sha and state. The fix is to check this durable integration record BEFORE calling _child_landing_evidence_block_reason. If the record shows state='integrated' and integrated_sha is reachable from the container/target branches, that's affirmative evidence and landing_reason should remain None.
---
author: oompah
created: 2026-08-02 16:31
---
Implementation: Added _child_has_durable_landing_evidence() method to check if a child's integrated_sha is reachable from container branches. Modified _mark_epic_merged() to call this before _child_landing_evidence_block_reason(). When durable evidence exists, the child is promoted instead of moved to Needs Human. Changes: oompah/orchestrator.py (2 edits), tests/test_epic_strategy.py (1 new test). All 220 epic_strategy tests pass.
---
<!-- COMMENTS:END -->
