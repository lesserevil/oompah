---
id: OOMPAH-733
type: task
status: In Progress
priority: null
title: Fail closed when a nested epic rebase target cannot be resolved
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T18:23:48.756544Z'
updated_at: '2026-08-03T18:28:05.834944Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d31efe1048fb2a727e1b2258c28d0d552076e4d24e28ffbc2fbd4061e24f07d0
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T18:26:35.076595+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** OOMPAH-733 is the only active (Open) task in the corpus.\
    \ All other tasks are in terminal Archived state and thus ineligible as duplicate\
    \ targets. Related archived tasks (OOMPAH-162, OOMPAH-163, OOMPAH-165) address\
    \ distinct epic branch routing and validation problems. OOMPAH-733 uniquely targets\
    \ the transient parent lookup failure path and its incorrect fallback to main,\
    \ which is not addressed by any existing task.\nI'll analyze OOMPAH-733 against\
    \ the project task corpus to determine if it's a duplicate of any existing task.\n\
    \n## Analysis\n\n**OOMPAH-733 Summary:**\nThe issue describes a problem where\
    \ nested epic rebase targets are incorrectly resolved to `main` when a transient\
    \ parent lookup failure occurs. The root cause is in `_resolve_epic_target_branch`,\
    \ which treats a failed `_resolve_parent_epic` lookup as proof the epic is top-level\
    \ and silently falls back to `project.default_branch`.\n\n**Key characteristics:**\n\
    - Nested epic with `parent_id` present\n- Transient parent lookup failure\n- Inappropriate\
    \ fallback to main instead of failing closed\n- References OOMPAH-633 (parent-only\
    \ policy) and OOMPAH-731 (direct-maintenance completion)\n\n**Corpus Review:**\n\
    \nScanning the provided task corpus for active (non-terminal) candidates:\n- **OOMPAH-733**\
    \ is the ONLY Open task\n- All other tasks listed are in **Archived** state (terminal)\n\
    \nReviewing related tasks by topic (all Archived):\n- **OOMPAH-162**: Stacked\
    \ child landing when merged to default branch \u2014 addresses different symptom\
    \ (merged-to-default behavior)\n- **OOMPAH-163**: Generated epic target branches\
    \ through dispatch \u2014 addresses branch allowlist bypass, not parent resolution\n\
    - **OOMPAH-165**: Shared epic landed detection before main merge \u2014 addresses\
    \ verifying merged PR target matches epic's resolved branch, not parent lookup\
    \ failure\n\n**Distinction from related tasks:**\nThese archived tasks handle\
    \ epic branch routing and validation, but none address the specific problem OOMPAH-733\
    \ targets: **transient parent epic resolution failure causing inappropriate main-branch\
    \ substitution**. OOMPAH-733 focuses on fail-closed error handling for parent\
    \ lookup, not the consequences of an already-wrong target.\n\n---\n\n**Focus handoff:\
    \ duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\n**Matches:\
    \ none**\n\n**Evidence:** OOMPAH-733 is the only active (Open) task in the corpus.\
    \ All other tasks are in terminal Archived state and thus i"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8a5fe562-c267-4707-8489-075b5971fcdc
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1711
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1711
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1711
    cost_usd: 0.0
    recorded_at: '2026-08-03T18:26:35.074433+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-733__20260803T182536Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-733
    source_sha: a7fc6676c44d6c88cf9a955002d51454929a2b20
    completed_at: '2026-08-03T18:26:35.114601+00:00'
---
## Summary

Live reproduction: EXOCOMP-245 was auto-filed as Rebase epic-EXOCOMP-135 onto main even though EXOCOMP-135 is a nested epic whose authoritative synchronization target is epic-EXOCOMP-127. The worker successfully force-pushed a main-based rebase, but the parent branch contains required exact prerequisite ancestry that main does not, so the Ready queue remains unclaimable. OOMPAH-633 allows nested-parent queue repair only when the target is the resolved authoritative parent; however, _resolve_epic_target_branch treats a transient _resolve_parent_epic lookup failure as proof that the epic is top-level and silently falls back to project.default_branch. Implementation scope: distinguish confirmed top-level epics from failed or incomplete parent resolution; when parent_id is present, resolve the parent from a canonical project snapshot or fail closed with a retryable diagnostic, never substitute main. Carry the resolved target branch as durable evidence into rebase-task creation, dispatch, prompt/workspace routing, completion, restart recovery, and dashboard diagnostics. Reject or supersede an existing active helper whose recorded target no longer matches the authoritative parent, without racing a worker or deleting recovery refs. Preserve the OOMPAH-633 parent-only policy, cooldown and duplicate fencing, exact force-with-lease behavior, and direct-maintenance completion from OOMPAH-731. Relevant code: _resolve_parent_epic, _resolve_epic_target_branch, nested integration-queue staleness repair, proactive rebase filing, helper task classification/prompting, and epic rebase state persistence. Required tests: reproduce a nested epic with parent_id where fetch_issue_detail transiently fails and assert no main-target helper is filed or dispatched; recover the parent lookup and assert exactly one helper targets origin/epic-parent; cover restart between failed lookup and recovery, stale wrong-target helper replacement, parent deletion or malformed metadata, true top-level epic main target, and unrelated epic denial. Run focused parallel-epic, epic-strategy, rebase maintenance, restart, and queue tests plus make test. Acceptance criteria: nested epic synchronization never mutates against main solely because parent lookup failed; EXOCOMP-245-style repairs converge on the authoritative parent target; ambiguous hierarchy remains retryable and visible without stranding Ready rows.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 18:25
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 18:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 18:26
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 4s
- Log: OOMPAH-733__20260803T182536Z.jsonl
---
author: oompah
created: 2026-08-03 18:27
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 18:27
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-03 18:28
---
Understanding: nested epic target resolution must distinguish confirmed top-level epics from failed parent lookup; I will trace helper filing, dispatch, persistence, restart, and diagnostics, then fail closed with retryable evidence and regression tests.
---
<!-- COMMENTS:END -->
