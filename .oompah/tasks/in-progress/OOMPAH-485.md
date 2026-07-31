---
id: OOMPAH-485
type: feature
status: In Progress
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
updated_at: '2026-07-31T03:57:51.463779Z'
work_branch: epic-OOMPAH-460--task-OOMPAH-485
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
oompah.agent_run_id: 12d2f031-2ac3-4c67-b4a7-13dc32a242dc
oompah.work_branch: epic-OOMPAH-460--task-OOMPAH-485
oompah.task_costs:
  total_input_tokens: 10241159
  total_output_tokens: 33135
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10190213
      output_tokens: 26948
      cost_usd: 0.0
    sonnet:
      input_tokens: 50910
      output_tokens: 858
      cost_usd: 0.0
    opus:
      input_tokens: 36
      output_tokens: 5329
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 210
    output_tokens: 5275
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:04:10.255551+00:00'
  - profile: default
    model: haiku
    input_tokens: 10190003
    output_tokens: 21673
    cost_usd: 0.0
    recorded_at: '2026-07-29T18:57:13.021445+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 50910
    output_tokens: 858
    cost_usd: 0.0
    recorded_at: '2026-07-29T18:58:19.083086+00:00'
  - profile: deep
    model: opus
    input_tokens: 36
    output_tokens: 5329
    cost_usd: 0.0
    recorded_at: '2026-07-29T19:03:20.123890+00:00'
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-460--task-OOMPAH-485
  base_branch: epic-OOMPAH-460
  base_sha: fd19b48db0293b02a267e7cf4f22cca5cf8073a1
  updated_at: '2026-07-31T03:57:48.668613+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-485__20260729T182724Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: frontend
    source_branch: epic-OOMPAH-460--task-OOMPAH-485
    source_sha: 290e834981114b9ad547a766920ec9165e96cb82
    completed_at: '2026-07-29T18:57:13.025970+00:00'
  - run_id: OOMPAH-485__20260729T185757Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: frontend
    source_branch: epic-OOMPAH-460--task-OOMPAH-485
    source_sha: 290e834981114b9ad547a766920ec9165e96cb82
    completed_at: '2026-07-29T18:58:19.087626+00:00'
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-1e6171cc9cf5
    project_id: proj-14849f1b
    task_id: OOMPAH-485
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 431a4147fe9037209bbceaa172f06be830158a34d144ccba150b84492aed2ee2
    authorized_by:
      version: 1
      identity: lesserevil
      source: api
    reason: 'Tracker reconciliation after operator-approved linearized recovery: each
      task implementation is preserved in OOMPAH-597 integrated head 44e5c5579, whose
      configured combined-tree gate passed 14,098 tests, 7 skipped, 1 expected xfail;
      the independent OOMPAH-597 auditor additionally passed 376 focused checks. The
      obsolete original per-child queue row cannot be replayed without duplicating/conflicting
      with the recovered content. This override closes bookkeeping only and does not
      waive code verification.'
    created_at: '2026-07-31T03:56:48.898727+00:00'
  version: 1
  pending_chain: []
  attempt_history: []
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
author: oompah
created: 2026-07-29 18:26
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 18:26
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-29 18:57
---
Agent completed successfully in 1862s (10211676 tokens)
---
author: oompah
created: 2026-07-29 18:57
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 3, Tool calls: 155
- Tokens: 10.2M in / 21.7K out [10.2M total]
- Cost: $0.0000
- Exit: normal, Duration: 31m 2s
- Log: OOMPAH-485__20260729T182724Z.jsonl
---
author: oompah
created: 2026-07-29 18:57
---
Agent completed without closing this issue (1862s (10211676 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-29 18:57
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 18:57
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-29 18:58
---
Agent completed successfully in 30s (51768 tokens)
---
author: oompah
created: 2026-07-29 18:58
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 3
- Tokens: 50.9K in / 858 out [51.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 30s
- Log: OOMPAH-485__20260729T185757Z.jsonl
---
author: oompah
created: 2026-07-29 18:58
---
Agent completed without closing this issue (30s (51768 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-29 18:58
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-29 18:58
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-29 19:02
---
Continuation review: prior run committed 2 changes (dcf6b5339, 290e83498) adding the In Validation board column and full terminal-audit detail UI to the dashboard, plus a template/JS static-contract test file. Verified today: (1) tests/test_dashboard_terminal_audit.py — all 12 tests pass (column rendering, task placement/filters, phase/attempt/revision/models/result rendering, safe escaping, safe API projection consumption, pending-as-status not alert, fail-closed override visibility, target+confirmation+reason validation, PATCH+audit_override request shape, loading/error paths, card+detail integration, responsive @720px + overflow-wrap hooks). (2) Neighboring suites still green: test_dashboard_conditional_columns, test_dashboard_board_reconciliation, test_dashboard_hide_merged, test_dashboard_detail_panel_width — 108 passed. Working tree clean; branch up to date with origin. Submitting.
---
author: oompah
created: 2026-07-29 19:02
---
Added the In Validation board column/count (using existing responsive board patterns) and the full terminal-audit detail block in the task detail panel — requested target, queued/running phase, attempt, evidence revision, contributor models, auditor provider/model, latest result, and actionable failure instructions. Added an owner-override control gated by explicit can_override/override_authorized/owner_override_allowed permission that requires target selection, an explicit confirmation checkbox, and a reason before PATCHing the issue API with audit_override/audit_override_target/audit_override_confirmed/audit_override_reason. Pending audits are rendered as role=status (not global alerts); long model names use overflow-wrap:anywhere and unknown fields display 'Unknown' via terminalAuditText/Identity helpers. Added tests/test_dashboard_terminal_audit.py (12 template/JS static-contract tests covering column rendering, task placement, every audit phase, safe escaping, safe API projection consumption, authorized/unauthorized override visibility, required target+confirmation+reason validation, PATCH request shape, loading/error paths, and responsive @720px + overflow-wrap hooks). Focused UI tests and neighboring dashboard suites all pass.
---
author: oompah
created: 2026-07-29 19:03
---
Run #3 [attempt=3, profile=deep, role=deep -> Claude/opus]
- Turns: 0, Tool calls: 30
- Tokens: 36 in / 5.3K out [5.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 28s
- Log: OOMPAH-485__20260729T185900Z.jsonl
---
author: oompah
created: 2026-07-31 03:56
---
Override by lesserevil: terminal transition to Done applied by project owner.

Reason: Tracker reconciliation after operator-approved linearized recovery: each task implementation is preserved in OOMPAH-597 integrated head 44e5c5579, whose configured combined-tree gate passed 14,098 tests, 7 skipped, 1 expected xfail; the independent OOMPAH-597 auditor additionally passed 376 focused checks. The obsolete original per-child queue row cannot be replayed without duplicating/conflicting with the recovered content. This override closes bookkeeping only and does not waive code verification.
---
author: oompah
created: 2026-07-31 03:56
---
Delivered through the verified OOMPAH-597 linearized recovery head 44e5c5579; stale original delivery row reconciled.
---
author: oompah
created: 2026-07-31 03:57
---
Integration found a rebase conflict on `epic-OOMPAH-460--task-OOMPAH-485`. Resolve it against `epic-OOMPAH-460`, run the required tests, push the same private branch, and `oompah task submit` it again.
---
author: oompah
created: 2026-07-31 03:57
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-31 03:57
---
Focus: Frontend Developer
---
<!-- COMMENTS:END -->
