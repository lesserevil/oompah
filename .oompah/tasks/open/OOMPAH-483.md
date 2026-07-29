---
id: OOMPAH-483
type: feature
status: Open
priority: 1
title: Detect and block terminal-state writes that bypass the coordinator
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-464
- OOMPAH-476
- OOMPAH-477
- OOMPAH-478
- OOMPAH-479
- OOMPAH-480
- OOMPAH-481
- OOMPAH-482
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:31.119782Z'
updated_at: '2026-07-29T02:01:40.087032Z'
work_branch: epic-OOMPAH-459
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e78ed4a0eb886be67172d00b18afaf76c115d5eb8d03c0af2f5e1c3159d895f7
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T02:01:37.169374+00:00'
  matched_identifiers: []
  evidence: "Let me check the only currently open task (OOMPAH-281) to ensure it's\
    \ not related to OOMPAH-483:\n\nOOMPAH-281 is about setting up a containerized\
    \ GitHub Actions runner \u2014 this is completely unrelated to detecting and blocking\
    \ terminal-state writes that bypass the coordinator.\n\nBased on my investigation,\
    \ I can now provide my findings:\n\n## Duplicate Investigation Summary\n\n**Investigation\
    \ Conducted:**\n1. Searched all `.oompah/tasks/` directories (archived, merged,\
    \ open, backlog) \u2014 found 280+ historical tasks\n2. Searched codebase for\
    \ keywords: terminal-state, coordinator, reconciliation, audit, close_issue, archive_issue,\
    \ bypass\n3. Searched documentation and plans directories\n4. Reviewed recent\
    \ tasks (OOMPAH-280, OOMPAH-281, OOMPAH-282)\n5. Checked for git references to\
    \ the epic and blocking tasks\n\n**Key Findings:**\n- OOMPAH-483 is a **brand\
    \ new task** on the `epic-OOMPAH-459` branch with blocking dependencies (OOMPAH-458,\
    \ OOMPAH-464, OOMPAH-476-482) that also don't exist in the current task database\n\
    - No existing tasks in the active task system (open, merged, archived, backlog)\
    \ cover the concepts described in OOMPAH-483:\n  - Periodic reconciliation pass\
    \ for terminal-state writes\n  - Coordinator pattern for authorizing state mutations\n\
    \  - Audit/override metadata tracking\n  - Regression tests preventing direct\
    \ writes to terminal states\n- The only currently open task (OOMPAH-281) is about\
    \ GitHub Actions CI runners \u2014 completely unrelated\n- No references to \"\
    coordinator\", \"terminal-state reconciliation\", \"audit comments\", or similar\
    \ concepts exist in the codebase or documentation\n\n**Conclusion:**\nOOMPAH-483\
    \ describes a new feature for detecting and blocking unauthorized terminal-state\
    \ writes. This is a unique requirement that does not duplicate any existing task\
    \ in the system.\n\n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight\
    \ verdict: no_duplicate\n\nMatches: none\n\nEvidence: Searched all active and\
    \ historical tasks (.oompah/tasks/ 280+ entries across archived/merged/o"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 814b53b9-4eba-491e-bbbf-6c6900a127df
oompah.work_branch: epic-OOMPAH-459
oompah.task_costs:
  total_input_tokens: 106
  total_output_tokens: 5117
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 106
      output_tokens: 5117
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 106
    output_tokens: 5117
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:01:37.168856+00:00'
---
## Summary

Implementation scope

Add a periodic reconciliation pass that compares future terminal records with current audit/override metadata and the grandfather baseline. An unaudited new Done/Merged/Archived record is moved to In Validation with the corresponding request chain and an audit comment. Handle direct forge label changes and writes from stale service versions idempotently. Add an AST/source regression test that finds tracker.update_issue terminal constants, close_issue, and archive_issue calls outside a small documented coordinator/persistence allowlist; replace or explicitly justify every current hit. Do not flag terminal-state comparisons or tests as mutations.

Tests

Cover direct tracker write, GitHub/GitLab label event, stale process race, grandfathered record, authorized override, changed fingerprint, repeated sweep, tracker failure, and static scanner positive/negative fixtures. Run focused tests and make test.

Acceptance criteria

A missed integration cannot silently create a trusted terminal state, and future direct terminal mutation code fails CI unless routed through the coordinator.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 02:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 02:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 48, Tool calls: 22
- Tokens: 106 in / 5.1K out [5.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 10s
- Log: OOMPAH-483__20260729T020030Z.jsonl
---
<!-- COMMENTS:END -->
