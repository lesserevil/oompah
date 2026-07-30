---
id: OOMPAH-605
type: bug
status: Open
priority: 1
title: Bootstrap reviewed terminal-audit fixes through a standalone recovery delivery
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T17:58:44.309909Z'
updated_at: '2026-07-30T17:59:20.789979Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a653af83a7e1bdd9024aa771b856539ffb3075bff5471de61b01a842771debb9
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 885e10da-f6ed-4b4e-9780-e296e883098f
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T17:59:11.989214+00:00'
  claim_expires_at: '2026-07-30T18:29:11.989214+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 11779e52-bff1-4cf6-bc59-6fd85575ca71
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
<!-- COMMENTS:END -->
