---
id: OOMPAH-725
type: task
status: In Progress
priority: null
title: Reject lifecycle-incompatible Merged overrides for shared-epic children
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T15:33:53.224136Z'
updated_at: '2026-08-03T16:02:37.772459Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ad31e0ee18386818195c444dd324348912d9da0616165babeecbcfae7117da8d
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T15:59:47.671629+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Closest reviewed tasks were OOMPAH-165 (epic landing\
    \ detection), OOMPAH-162 (stacked child landing), and OOMPAH-168 (shared workflow\
    \ simplification); all are terminal and address different behavior.\nFocus handoff:\
    \ duplicate_detector  \nDuplicate preflight verdict: no_duplicate  \nMatches:\
    \ none  \n\nEvidence: Closest reviewed tasks were OOMPAH-165 (epic landing detection),\
    \ OOMPAH-162 (stacked child landing), and OOMPAH-168 (shared workflow simplification);\
    \ all are terminal and address different behavior."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: fd4cb031-3bad-430c-a1bd-d0f01149db73
oompah.task_costs:
  total_input_tokens: 50391
  total_output_tokens: 395
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 50391
      output_tokens: 395
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 50391
    output_tokens: 395
    cost_usd: 0.0
    recorded_at: '2026-08-03T15:59:47.668765+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-725__20260803T155925Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-725
    source_sha: d510748342777dd4748070d83391ffb0eae40091
    completed_at: '2026-08-03T15:59:47.680961+00:00'
---
## Summary

Live reproduction: EXOCOMP-240 is an auto-filed rebase maintenance task parented by shared epic EXOCOMP-130. Its completion auditor passed the required Done transition. A later project-owner terminal override changed the child to Merged even though its work landed only on epic-EXOCOMP-130, not the project default branch. The epic rollup correctly rejects that evidence and now logs EXOCOMP-240=Merged (requires Done), so a superficially more terminal state indefinitely blocks the parent.

Implementation scope:
- Enforce shared-epic child lifecycle compatibility at every terminal transition boundary, including project-owner audit override, ACP override, API/CLI set-status, recovery, and maintenance/rebase completion.
- A child whose accepted work is contained only in its parent epic branch may reach audited Done but may not reach Merged until the parent review lands on the configured target branch.
- Auto-filed epic rebase/maintenance tasks must use Done as their successful terminal target and must not enqueue or invite a second Merged transition merely because they mutate the epic branch directly.
- Preserve legitimate owner override authority for evidence-backed emergency recovery, but reject structurally impossible Merged evidence with a precise conflict explaining the required parent landing.
- Add reconciliation for existing incompatible Merged children: when Done audit evidence exists and the parent has not landed, safely restore Done without rerunning implementation or losing audit history.

Relevant code: terminal_transition_coordinator owner overrides, API/ACP terminal boundaries, shared-epic strategy validation, auto-filed rebase completion, epic rollup reconciliation, and terminal-audit enforcement recovery.

Required tests:
- Reproduce EXOCOMP-240: maintenance child passes Done, owner requests Merged before parent landing, request is rejected and parent completion still accepts the child as Done.
- Cover ordinary shared-epic children, nested epics, default-branch landing followed by legitimate Merged, API and ACP owner overrides, restart recovery, and legacy incompatible records.
- Prove the repair preserves the completed Done audit and cancels no unrelated audit.
- Run focused terminal-override, transition-coordinator, epic-strategy, maintenance/rebase, lifecycle, and terminal-audit-enforcement suites plus make test.

Acceptance criteria:
- A shared-epic child cannot enter Merged solely because its commit is on the epic branch.
- Existing EXOCOMP-240-style records converge to audited Done and no longer block rollup.
- Legitimately target-landed children and top-level tasks can still reach Merged through normal audited or owner-override paths.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 15:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 15:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 15:59
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.4K in / 395 out [50.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 33s
- Log: OOMPAH-725__20260803T155925Z.jsonl
---
author: oompah
created: 2026-08-03 16:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 16:02
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->
