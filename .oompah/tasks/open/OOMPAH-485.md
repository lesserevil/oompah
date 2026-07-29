---
id: OOMPAH-485
type: feature
status: Open
priority: 1
title: Add In Validation and terminal-audit details to the dashboard
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-484
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:08:24.220262Z'
updated_at: '2026-07-29T02:04:13.542089Z'
work_branch: epic-OOMPAH-460
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f9d89ebd05e20449a1d7e84fd785a177730fdaa2fa8b119f3e7ce82caf5e0adc
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T02:04:10.256037+00:00'
  matched_identifiers: []
  evidence: 'Based on my comprehensive investigation of the codebase, I have thoroughly
    searched for duplicate tasks:


    **Search Methodology:**

    1. Scanned all `.oompah/tasks` directories (open/, backlog/, archived/, merged/)

    2. Searched for keywords: "validation", "audit", "terminal-audit", "auditor",
    "override", "In Validation", "dashboard column", "responsive board"

    3. Checked project documentation (docs/, plans/, README.md, WORKFLOW.md)

    4. Examined codebase for existing implementations (src/, oompah/, .github/)

    5. Reviewed task metadata in archived and merged tasks


    **Key Findings:**

    - No existing task files in the OOMPAH-4xx range were found (latest indexed task:
    OOMPAH-282)

    - No references to "In Validation" column, terminal-audit details, or auditor
    override controls

    - No existing dashboard validation/audit UI features in the codebase

    - The single Dashboard.tsx component contains only "useEffect cleanup" stub content

    - No archived or merged tasks cover work-status dashboards, validation tracking,
    or audit overrides


    **Closest Reviewed Candidates:**

    - OOMPAH-281 (GitHub Actions runner setup) - completely different scope

    - OOMPAH-282 (state_branch_migration error) - backend bug, not UI feature


    ---


    **Focus handoff: duplicate_detector**


    **Duplicate preflight verdict: no_duplicate**


    **Matches: none**


    **Evidence:** Comprehensive search of `.oompah/tasks` across all states (open,
    backlog, archived, merged), project documentation, and codebase found no existing
    active tasks or implementations related to dashboard "In Validation" columns,
    terminal-audit details display, auditor provider/model information, or authorized
    owner override controls. This is a new feature request with no active duplicate.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 1a92387f-66be-4904-bf9f-d8eaf75859c5
oompah.work_branch: epic-OOMPAH-460
oompah.task_costs:
  total_input_tokens: 210
  total_output_tokens: 5275
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 210
      output_tokens: 5275
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 210
    output_tokens: 5275
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:04:10.255551+00:00'
---
## Summary

Implementation scope

Add an In Validation board column/count using existing responsive board patterns. In task detail, show requested target, queued/running phase, attempt, evidence revision, contributor models, auditor provider/model, latest result, and actionable failure instructions. Add an explicit owner override control only for authorized users; require target, confirmation, and reason, and call the existing terminal status API with audit_override. Show normal pending audits as status, not alerts. Handle long model names and missing/unknown values accessibly.

Tests

Add template/JavaScript tests for column rendering, task placement, every audit phase, safe escaping, authorized/unauthorized override visibility, required reason validation, API request shape, loading/error behavior, responsive layout hooks, and no duplicate terminal columns. Run focused UI tests and make test.

Acceptance criteria

A user can see why work is validating, which independent model is checking it, what failed, and deliberately perform an authorized documented override without editing tracker labels.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 02:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 02:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 62, Tool calls: 25
- Tokens: 210 in / 5.3K out [5.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 25s
- Log: OOMPAH-485__20260729T020248Z.jsonl
---
<!-- COMMENTS:END -->
