---
id: OOMPAH-748
type: bug
status: In Progress
priority: 1
title: Break nested-epic rollup cycle between Done child epics and parent landing
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T00:41:04.498057Z'
updated_at: '2026-08-04T00:45:09.844272Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c9fbcc861c522c73c72cc1ac5637b98b071961b57276069044961a27cbe66c16
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T00:43:21.382931+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Closest tasks OOMPAH-165 and OOMPAH-162 are terminal\
    \ and excluded; no active peer covers this nested-epic rollup cycle.\nFocus handoff:\
    \ duplicate_detector  \nDuplicate preflight verdict: no_duplicate  \nMatches:\
    \ none  \n\nEvidence: Closest tasks OOMPAH-165 and OOMPAH-162 are terminal and\
    \ excluded; no active peer covers this nested-epic rollup cycle."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8cb04cf8-d8c1-45ec-a65d-d352e6ade632
oompah.task_costs:
  total_input_tokens: 46205
  total_output_tokens: 195
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46205
      output_tokens: 195
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46205
    output_tokens: 195
    cost_usd: 0.0
    recorded_at: '2026-08-04T00:43:18.192127+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-748__20260804T004257Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-748
    source_sha: 4ea94b151a09758c57a93c8710c05f28a49bcc2a
    completed_at: '2026-08-04T00:43:18.203330+00:00'
---
## Summary

Triggered by: EXOCOMP-128

Live reproduction: EXOCOMP-128 passed a Merged audit after PR 21 landed its nested epic branch into epic-EXOCOMP-127, but lifecycle validation rejects Merged until EXOCOMP-127 lands on main. At the same time, EXOCOMP-127 auto-close refuses to proceed until nested child EXOCOMP-128 is Merged. This creates a closed lifecycle cycle even though the child branch is landed on its immediate parent target. Implementation scope: define target-relative terminal semantics for nested shared epics so the parent rollup can accept an independently audited child that is landed on the immediate parent branch, without marking the root epic landed on main prematurely. Reconcile epic auto-close, terminal validation, rollup status, and audit evidence around one rule; preserve the safety constraints from OOMPAH-725. Relevant code includes nested-epic target resolution, lifecycle transition validation, _label_merged_epics, epic rollup, and epic auto-close in oompah/orchestrator.py and transition gates. Required tests: nested epic landed on parent but parent not main; root parent then opens and lands; genuinely unlanded nested child; wrong target; deleted or rebased refs with trusted evidence; override and restart reconciliation. Acceptance criteria: no state cycle exists between a nested child and its parent; proven immediate-target landing naturally unblocks the parent; premature root-level Merged remains impossible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 00:42
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 00:42
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 00:43
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.2K in / 195 out [46.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 33s
- Log: OOMPAH-748__20260804T004257Z.jsonl
---
author: oompah
created: 2026-08-04 00:44
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 00:44
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-04 00:45
---
**Understanding:** The issue describes a deadlock between nested epics and their parents. When a nested child epic (e.g., EXOCOMP-128) lands its branch on the parent epic target (EXOCOMP-127), the child should be able to reach Merged state without requiring the parent to land on main first. Currently: child can't be Merged until parent lands on main, but parent can't auto-close until child is Merged. The fix requires target-relative terminal semantics so a child landed on its immediate parent branch can be marked Merged independently. This unblocks parent progress without prematurely marking the root as landed on main. Scope: orchestrator.py (nested-epic target resolution, lifecycle validation, _label_merged_epics, epic rollup, auto-close logic). Will need comprehensive tests for various nested scenarios.
---
<!-- COMMENTS:END -->
