---
id: OOMPAH-725
type: task
status: Open
priority: null
title: Reject lifecycle-incompatible Merged overrides for shared-epic children
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T15:33:53.224136Z'
updated_at: '2026-08-03T15:59:50.784089Z'
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
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: edffea8c-c5cc-4e23-a040-6f79dfe6caff
  claim_owner: 2dcc53e1-cdcd-4522-a08d-de6ce4222a8c
  claimed_at: '2026-08-03T15:59:04.538859+00:00'
  claim_expires_at: '2026-08-03T16:29:04.538859+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 79b3101a-3ad3-4e9a-af95-625d03bfef25
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
<!-- COMMENTS:END -->
