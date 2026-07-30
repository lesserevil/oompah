---
id: OOMPAH-605
type: bug
status: In Review
priority: 1
title: Bootstrap reviewed terminal-audit fixes through a standalone recovery delivery
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T17:58:44.309909Z'
updated_at: '2026-07-30T18:07:05.269752Z'
work_branch: OOMPAH-605
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/593
review_number: '593'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a653af83a7e1bdd9024aa771b856539ffb3075bff5471de61b01a842771debb9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T18:01:23.888860+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Reviewed active OOMPAH-584, OOMPAH-585, OOMPAH-589, OOMPAH-598, OOMPAH-599,
    and OOMPAH-604. They cover the parent recovery epic, component fixes, generic
    standalone delivery, and permanent liveness invariant, but none duplicates this
    one-off bootstrap delivery through a broken control plane.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: f601b8e9-a776-4b45-b5b7-10c8337cdb36
oompah.task_costs:
  total_input_tokens: 1204783
  total_output_tokens: 5398
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1204783
      output_tokens: 5398
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1204783
    output_tokens: 5398
    cost_usd: 0.0
    recorded_at: '2026-07-30T18:01:23.887773+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-605__20260730T175922Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-605
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T18:01:23.897031+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/593
oompah.review_number: '593'
oompah.work_branch: OOMPAH-605
oompah.target_branch: main
---
## Summary

Triggered by: OOMPAH-584

Implementation scope

Break the current self-hosting control-plane deadlock without editing tracker Markdown or bypassing the configured quality gate. Create a standalone recovery branch from current main containing the exact already-reviewed OOMPAH-589 auditor candidate/endpoint fixes and OOMPAH-604 current-record owner-override fix, deliver it directly to main through the normal pull-request path, restart the service with the Makefile lifecycle target, and verify the terminal-audit lane resumes. Preserve the original epic branches so their remaining children can integrate normally. Record the bootstrap procedure in the operator runbook as the recovery path when a control-plane fix is itself blocked behind the broken control plane. Relevant code is the reviewed diff on origin/epic-OOMPAH-585; documentation belongs in docs/operator-runbook.md.

Tests

Run focused terminal-audit candidate, provider, orchestrator, coordinator, override, API, and CLI tests. Run the configured complete make test gate on the exact recovery head before delivery. After restart, verify an eligible pending audit launches with an absolute endpoint, no /chat/completions URL error recurs, and at least one previously pending In Validation task advances or accepts a valid owner override.

Acceptance criteria

The reviewed OOMPAH-589 and OOMPAH-604 fixes are present on main and in the running service; the current audit deadlock is broken; no quality gate, independent-audit evidence, or tracker-write rule is bypassed; the recovery is repeatable and auditable; OOMPAH-599 remains responsible for the permanent no-stranded-work invariant.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 17:58
---
Direct operator implementation claimed because the running terminal-audit control plane cannot deliver its own reviewed repair epic. This is the explicit bootstrap recovery; OOMPAH-599 remains the permanent liveness invariant check.
---
author: oompah
created: 2026-07-30 17:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 17:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 18:01
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 18
- Tokens: 1.2M in / 5.4K out [1.2M total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 5s
- Log: OOMPAH-605__20260730T175922Z.jsonl
---
author: oompah
created: 2026-07-30 18:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 18:01
---
Focus: Auth Http Default Specialist
---
author: oompah
created: 2026-07-30 18:01
---
**Understanding**: This is a bootstrap recovery task to break the self-hosting control-plane deadlock. The terminal-audit control plane cannot deliver its own reviewed repairs, so we need to create a standalone recovery branch from main containing the already-reviewed OOMPAH-589 (auditor candidate/endpoint fixes) and OOMPAH-604 (owner-override fix) from origin/epic-OOMPAH-585. After delivery and restart, the terminal-audit lane should resume. My approach: (1) Explore epic-OOMPAH-585 to find the reviewed fixes, (2) Extract and apply those fixes to a recovery branch from main, (3) Run focused tests and full make test gate, (4) Document the bootstrap procedure in docs/operator-runbook.md, (5) Verify the fixes work after restart.
---
author: oompah
created: 2026-07-30 18:07
---
Operator handoff: recovery branch OOMPAH-605 is already complete and pushed at cfe2916c5; focused tests passed (698), exact full make test passed (13,724 passed, 7 skipped), and PR #593 is running CI. Do not rewrite or push the branch. Inspect/verify only, then exit cleanly.
---
<!-- COMMENTS:END -->
