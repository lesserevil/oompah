---
id: OOMPAH-826
type: bug
status: In Progress
priority: 1
title: Gate changed heads before adopting an existing open review
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-05T12:59:13.179121Z'
updated_at: '2026-08-05T19:51:46.242503Z'
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
oompah.agent_run_id: 39e5cf5c-2d5b-4653-8298-fc8467545344
oompah.task_costs:
  total_input_tokens: 140
  total_output_tokens: 5194
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 140
      output_tokens: 5194
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 6
    output_tokens: 1061
    cost_usd: 0.0
    recorded_at: '2026-08-05T18:19:18.058681+00:00'
  - profile: deep
    model: opus
    input_tokens: 134
    output_tokens: 4133
    cost_usd: 0.0
    recorded_at: '2026-08-05T19:42:09.613536+00:00'
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
author: oompah
created: 2026-08-05 18:28
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-05 18:28
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-05 18:48
---
Understanding: Three call sites in oompah/orchestrator.py adopt an existing open review without running the exact-head branch quality gate first:

1. \`_ensure_review_exists\` cached path (~line 21455) - iterates \`_reviews_cache\`, calls \`_mark_task_in_review\` when a matching open review is found.
2. \`_ensure_review_exists\` live path (~line 21547) - live provider fetch, same pattern.
3. \`_reconcile_standalone_ready_to_integrate_tasks\` (~line 8959) - calls \`_adopt_standalone_open_review_owned\` for an existing open PR.
4. \`adopt_open_review_from_webhook\` (line 4139) - updates task to In Review inside the transition mutex, no gate.

The epic path (\`_open_epic_main_prs\` ~line 18313) was already fixed for OOMPAH-520 with the exact pattern I need to replicate: capacity adoption first, then \`_review_quality_gate_passes\`, then mark In Review.

Plan:
- Insert \`_review_quality_gate_passes\` between capacity adoption and \`_mark_task_in_review\` in the two \`_ensure_review_exists\` paths.
- Insert the gate call before \`_adopt_standalone_open_review_owned\`.
- Refactor \`adopt_open_review_from_webhook\` to run the gate on the resolved current head after CAS validation but before the metadata write and In Review update. Gate cache on head SHA keeps unchanged heads single-flight; failure routes through the existing NEEDS_CI_FIX flow via \`_record_quality_gate_failure\`.
- Tests: update \`test_existing_open_review_is_reused_idempotently\` and add coverage for changed-head gating, unchanged-head PASS reuse, gate failure preserving the review, and webhook adoption gating.
---
author: oompah
created: 2026-08-05 19:42
---
Agent stalled — no productive actions (writes/commands) for 10 consecutive turns (4417s (4267 tokens)). Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-05 19:42
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/opus]
- Turns: 124, Tool calls: 87
- Tokens: 134 in / 4.1K out [4.3K total]
- Cost: $0.0000
- Exit: stalled, Duration: 1h 13m 37s
- Log: OOMPAH-826__20260805T182850Z.jsonl
---
author: oompah
created: 2026-08-05 19:43
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-05 19:43
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-05 19:44
---
Understanding: Continuing the preserved OOMPAH-826 review branch as a CI-fix pass. I will inspect the existing orchestrator/test changes, fetch and fast-forward the same branch, read the original PR check logs to identify the concrete failure, reproduce it with the relevant Makefile-backed focused tests, and apply only the minimal exact-head review-gating correction before pushing and submitting.
---
author: oompah
created: 2026-08-05 19:48
---
Discovery: PR #721’s failed run 31005918588 confirms the trigger: local evidence existed for 74c4b71c, forge CI failed test_close_gate.py, and the repaired 11c75e6c rerun passed. OOMPAH-826 itself has no remote PR/run yet. The preserved patch gates four adoption sites, but focused standalone recovery currently has 3 failures because restart/race/metadata tests still assert that an existing review skips the gate. More importantly, exact-head gating must be tested through the durable BranchQualityGate cache and the authority CAS, not only by changing one mock assertion; the unrelated uv.lock refresh will be removed.
---
<!-- COMMENTS:END -->
