---
id: OOMPAH-826
type: bug
status: Open
priority: 1
title: Gate changed heads before adopting an existing open review
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T12:59:13.179121Z'
updated_at: '2026-08-05T18:19:25.048182Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9f01d5fa0cbf46c07fb161dc8acb5f98101fda5b10483836a60aa8f789ac25be
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T18:19:18.060395+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Every peer task in the supplied corpus is in a terminal\
    \ Archived state and therefore ineligible as an active duplicate target per the\
    \ screening contract. The closest topical peers are the archived OOMPAH-520 referenced\
    \ in the description itself (fixed only the existing epic-review reconciliation\
    \ path, explicitly noted as a partial predecessor \u2014 not the standalone/integration-entry\
    \ gap being fixed here), and archived OOMPAH-165 (shared-epic landed detection\
    \ before main merge \u2014 related orchestrator/epic-review reconciliation but\
    \ scoped to landed-target verification, not local exact-head quality-gate evidence\
    \ before adopting an open review). Other archived orchestrator/epic tasks (OOMPAH-162,\
    \ OOMPAH-163, OOMPAH-168) touch epic branch/dispatch logic but do not address\
    \ the \"existing open review adoption skips _review_quality_gate_passes on a changed\
    \ head\" defect described in OOMPAH-826. No active (non-terminal) peer task in\
    \ the corpus describes the same underlying problem, so this is not a \nFocus handoff:\
    \ duplicate_detector\nDuplicate preflight verdict: no_duplicate\nMatches: none\n\
    \nEvidence: Every peer task in the supplied corpus is in a terminal Archived state\
    \ and therefore ineligible as an active duplicate target per the screening contract.\
    \ The closest topical peers are the archived OOMPAH-520 referenced in the description\
    \ itself (fixed only the existing epic-review reconciliation path, explicitly\
    \ noted as a partial predecessor \u2014 not the standalone/integration-entry gap\
    \ being fixed here), and archived OOMPAH-165 (shared-epic landed detection before\
    \ main merge \u2014 related orchestrator/epic-review reconciliation but scoped\
    \ to landed-target verification, not local exact-head quality-gate evidence before\
    \ adopting an open review). Other archived orchestrator/epic tasks (OOMPAH-162,\
    \ OOMPAH-163, OOMPAH-168) touch epic branch/dispatch logic but do not address\
    \ the \"existing open review adoption skips _review_quality_gate_passes on a changed\
    \ head\" defect described in OOMPAH-826. No active (non-terminal) peer task in\
    \ the corpus describes the same underlying problem, so this is not a duplicate."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3afe0e24-ff78-4f66-a922-91a298edda72
oompah.task_costs:
  total_input_tokens: 6
  total_output_tokens: 1061
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 6
      output_tokens: 1061
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 6
    output_tokens: 1061
    cost_usd: 0.0
    recorded_at: '2026-08-05T18:19:18.058681+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-826__20260805T181747Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: opus
    focus: duplicate_detector
    source_branch: OOMPAH-826
    source_sha: b53bdbc77c7a50d332a97096ebc85d7923280854
    completed_at: '2026-08-05T18:19:18.079856+00:00'
---
## Summary

Triggered by: OOMPAH-825

Live reproduction on OOMPAH-825 PR #721 on 2026-08-05: exact head 74c4b71c passed the local branch gate, forge CI failed, a test-only repair advanced the branch to 11c75e6c, and explicit resubmission immediately moved the task to In Review while validation_resources and quality_gates remained idle. The existing-review path in oompah/orchestrator.py adopts a live open review and calls _mark_task_in_review before _review_quality_gate_passes, so the changed repaired head has no local exact-head gate evidence. This is the standalone/integration-entry analogue of archived OOMPAH-520, which fixed only existing epic-review reconciliation. Implementation scope: bind existing open review adoption to its exact current source head/generation; before marking an accepted submission In Review or allowing merge reconciliation, require _review_quality_gate_passes for the submitted exact head, reusing same-head PASS only; preserve the open review while the gate runs/fails, route a true gate failure through the normal retryable Needs CI Fix flow, and avoid duplicate gates/reviews/comments across webhook, polling, resubmit, and restart races. Relevant code: oompah/orchestrator.py existing live-review adoption in integration delivery, standalone Ready review recovery, review-head metadata/authorities, quality-gate outcome/cache fencing. Required tests: OOMPAH-825 case with existing open PR old gate PASS then changed CI-fix head; changed head must run once before In Review, unchanged head reuses PASS, gate failure never merges/adopts, concurrent webhook+submit coalesces, restart preserves exact-head evidence, and epic behavior from OOMPAH-520 remains intact. Acceptance: every accepted current review head has passing local exact-head evidence before In Review/merge eligibility; forge CI alone cannot bypass the configured branch gate; no duplicate review is created; focused suites and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 18:17
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-08-05 18:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 18:19
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/opus]
- Turns: 2, Tool calls: 0
- Tokens: 6 in / 1.1K out [1.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 53s
- Log: OOMPAH-826__20260805T181747Z.jsonl
---
<!-- COMMENTS:END -->
