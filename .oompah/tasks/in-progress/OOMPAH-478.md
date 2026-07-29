---
id: OOMPAH-478
type: feature
status: In Progress
priority: 1
title: Route epic rollup, child Done, and epic close transitions through audits
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:26.329329Z'
updated_at: '2026-07-29T18:30:28.164291Z'
work_branch: epic-OOMPAH-459--task-OOMPAH-478
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ab86b60bea92b12dbe85f111788a91ca686b0760b5299075160d7f27c6439cc4
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:37:17.162767+00:00'
  matched_identifiers: []
  evidence: "Based on my investigation, let me provide my findings:\n\n## Duplicate\
    \ Investigation Complete\n\nI have searched comprehensively for existing tasks\
    \ that might duplicate OOMPAH-478's scope:\n\n**Search Strategy:**\n- Scanned\
    \ all `.oompah/tasks/` directories (open, merged, archived)\n- Searched for keywords:\
    \ \"epic,\" \"rollup,\" \"audit,\" \"terminal,\" \"child,\" \"Done,\" \"close,\"\
    \ \"transition\"\n- Reviewed relevant design docs: `terminal-transition-coordinator.md`,\
    \ `multi-branch-support.md`\n- Examined test files: `test_epic_strategy.py`, `test_epic_auto_close.py`,\
    \ `test_terminal_transition_coordinator.py`\n- Checked blocker task IDs (OOMPAH-475,\
    \ OOMPAH-458) in tracker\n\n**Key Findings:**\n- OOMPAH-478, OOMPAH-475, OOMPAH-458,\
    \ and OOMPAH-459 do not exist as native tasks in `.oompah/tasks/`\n- Only one\
    \ active open task exists: OOMPAH-281 (self-hosted runner infrastructure)\n- The\
    \ terminal transition coordinator infrastructure is designed (plans/ docs) and\
    \ partially implemented\n- Epic strategy and auto-close exist in the codebase\
    \ but do NOT route through the audit system\n- No existing tests cover \"routing\
    \ epic rollup / child Done / epic close transitions through audits\"\n- The closest\
    \ related tasks (OOMPAH-281, OOMPAH-280, OOMPAH-279) deal with unrelated infrastructure\n\
    \n**Closest Reviewed Candidates (All Terminal or Unrelated):**\n- Merged OOMPAH-271-280:\
    \ Release delivery, epic staleness, UI features \u2014 none cover audit routing\
    \ for epic transitions\n- Archived OOMPAH-1-276: Various historical tasks, none\
    \ address routing epic rollup through audits\n\n**Conclusion:**\nOOMPAH-478 describes\
    \ a unique feature: integrating the existing terminal transition coordinator infrastructure\
    \ with epic rollup reconciliation, stale child completion, and epic auto-close\
    \ logic. No active task covers this scope.\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\
    \ Comprehensive scan of `.oompah/tasks/` (all states), keyword searches in plans/\
    \ and tests"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
oompah.agent_run_id: b2111678-117c-49b0-9e2e-bcfe926acf56
oompah.work_branch: epic-OOMPAH-459--task-OOMPAH-478
oompah.task_costs:
  total_input_tokens: 396
  total_output_tokens: 10399
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 396
      output_tokens: 10399
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 162
    output_tokens: 4648
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:33:39.043297+00:00'
  - profile: default
    model: haiku
    input_tokens: 234
    output_tokens: 5751
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:37:17.161698+00:00'
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-459--task-OOMPAH-478
  base_branch: epic-OOMPAH-459
  base_sha: 65c8e4725fe931bf0fa9c3357d153ba003ad03c4
  updated_at: '2026-07-29T18:26:12.657814+00:00'
---
## Summary

Implementation scope

Replace terminal writes in epic rollup reconciliation, stale In Review child completion, parent auto-close, and epic/child merged promotion with coordinator requests. In Validation children count as nonterminal and block rollup landing. A parent cannot enter Done until every required child has a current passed Done audit. A parent Merged request must chain its own Done audit when missing and then run target landing audit. Preserve nested/shared epic branch and landing-evidence gates. Do not let rollup reconciliation overwrite In Validation or audit:repair-needed.

Tests

Cover standalone epic, shared children, stale In Review child to Done, nested epics, child In Validation blocking parent, missing child audit, parent Done/Merged audit chains, independently merged child, existing review-repair states, and idempotent repeated ticks. Run epic strategy/rollup tests and make test.

Acceptance criteria

No epic or child is terminalized by rollup alone; each terminal meaning has the correct current audit and existing branch containment safeguards still apply.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:30
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:33
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 49, Tool calls: 19
- Tokens: 162 in / 4.6K out [4.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 48s
- Log: OOMPAH-478__20260729T013057Z.jsonl
---
author: oompah
created: 2026-07-29 01:35
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:37
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 65, Tool calls: 33
- Tokens: 234 in / 5.8K out [6.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 54s
- Log: OOMPAH-478__20260729T013526Z.jsonl
---
author: oompah
created: 2026-07-29 18:26
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 18:26
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-29 18:28
---
Understanding: Epic rollup transitions need to route through coordinator audits instead of direct terminal writes. Key changes:
1. Replace direct terminal writes in rollup reconciliation, stale In Review child completion, parent auto-close, and epic/child merged promotion with coordinator requests
2. Ensure In Validation children block rollup landing
3. Parent Done requires all required children to have current passed Done audits
4. Parent Merged must chain own Done audit when missing
5. Preserve existing branch/landing-evidence gates

Starting discovery phase to locate rollup, audit, and coordinator code.
---
author: oompah
created: 2026-07-29 18:30
---
Discovery: Located relevant code:
- orchestrator.py _reconcile_epic_rollup_statuses (line 5172): Currently uses tracker.update_issue() directly for all states
- terminal_audit.py: Defines audit record types and terminal states
- terminal_transition_coordinator.py: Coordinator for staging terminal transitions
- orchestrator.py request_terminal_transition (line 2320): Existing method to route through coordinator
- statuses.py epic_rollup_state: Returns rolled state (DONE, MERGED, or nonterminal)

Key insight: Need to replace direct tracker.update_issue() calls with coordinator.request_transition() for terminal states (DONE, MERGED, ARCHIVED) while keeping nonterminal state updates direct. Must skip reconciliation when epic is In Validation or has audit:repair-needed label.
---
<!-- COMMENTS:END -->
