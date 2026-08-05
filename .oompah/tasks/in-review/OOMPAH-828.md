---
id: OOMPAH-828
type: bug
status: In Review
priority: 1
title: Treat applied Archived audit results as final lifecycle no-ops
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T13:24:20.492002Z'
updated_at: '2026-08-05T20:49:57.069585Z'
work_branch: OOMPAH-828
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/724
review_number: '724'
review_head: a5545b61a8db17a99655f81dfdafa7f5741c243c
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 87becaec0c8737f6d1f62cf3a5548d643724ff146f5b3c463e1e379737672048
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T18:20:05.408840+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-828 addresses a unique production bug in archived\
    \ audit result lifecycle enforcement where applied Archived result intents are\
    \ incorrectly rejected by `_lifecycle_terminal_authorities` due to fingerprint\
    \ domain mismatch (request-shaped vs. issue-shaped). All 33 similarity candidates\
    \ in the corpus are in terminal states and focus on unrelated areas: epic workflow\
    \ strategies, release automation, dashboard controls, and GitHub integration.\
    \ No active task covers the audit fingerprinting, lifecycle finality, or terminal\
    \ authority validation issues described in OOMPAH-828.\nLooking at OOMPAH-828\
    \ and comparing it against the supplied project task corpus, I need to determine\
    \ if this is a duplicate of an existing active task.\n\n**OOMPAH-828 Analysis:**\n\
    - Status: Open (active, not terminal)\n- Type: Bug, Priority 1\n- Focus: Archived\
    \ audit result handling in lifecycle enforcement\n- Root cause: Fingerprint mismatch\
    \ between `request_archived_audit` (uses `compute_evidence_fingerprint(requirements_text=reason)`)\
    \ and `_lifecycle_terminal_authorities` (requires `compute_issue_evidence_fingerprint(current\
    \ issue)`)\n- Problem: Applied Archived result intents are rejected as `lifecycle_metadata_not_finalized`\
    \ despite already being applied\n- Relevant code: `archived_audit_requests.py`,\
    \ `terminal_audit_enforcement.py`, terminal metadata/result-intent schemas\n\n\
    **Corpus Examination:**\nThe provided corpus includes 33 similarity candidates,\
    \ all in terminal states (Archived or Done). I reviewed each:\n\n- **OOMPAH-10\
    \ through OOMPAH-15:** GitHub integration, dashboard, error handling \u2014 unrelated\n\
    - **OOMPAH-156 through OOMPAH-171:** Epic workflow strategies, draft epics, dashboard\
    \ controls \u2014 unrelated\n- **OOMPAH-172 through OOMPAH-180:** Release automation\
    \ (addendums), PR reconciliation, branch strategies \u2014 unrelated\n- **OOMPAH-17,\
    \ OOMPAH-18, OOMPAH-3:** Release train, documentation, branch rebase \u2014 unrelated\n\
    \n**Key Findings:**\nNone of the candidates address:\n- Archived audit result\
    \ finality\n- Evidence fingerprint domains and validation\n- Terminal authority\
    \ enforcement for Archived records\n- Applied result-intent handling in lifecycle\
    \ batches\n- Target-aware lifecycle metadata\n\nOOMPAH-828 references OOMPAH-825\
    \ as its trigger and OOMPAH-452/453/455/456 as production lifecycle rows, but\
    \ these are not in the provided corpus. The task describes a highly specific production\
    \ bug with no existing task covering the same lifecycle enforcement issue.\n\n\
    ---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: OOMPAH-828 addr"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 9cca355f-357c-4f01-a103-1685fae57231
oompah.task_costs:
  total_input_tokens: 1068
  total_output_tokens: 43662
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 936
      output_tokens: 2594
      cost_usd: 0.0
    opus:
      input_tokens: 132
      output_tokens: 41068
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2369
    cost_usd: 0.0
    recorded_at: '2026-08-05T18:20:05.407374+00:00'
  - profile: default
    model: haiku
    input_tokens: 926
    output_tokens: 225
    cost_usd: 0.0
    recorded_at: '2026-08-05T19:42:16.553408+00:00'
  - profile: deep
    model: opus
    input_tokens: 132
    output_tokens: 41068
    cost_usd: 0.0
    recorded_at: '2026-08-05T20:32:03.185943+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-828__20260805T181810Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-828
    source_sha: b53bdbc77c7a50d332a97096ebc85d7923280854
    completed_at: '2026-08-05T18:20:05.427853+00:00'
  - run_id: OOMPAH-828__20260805T194409Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: opus
    focus: oompah_tests
    source_branch: OOMPAH-828
    source_sha: a5545b61a8db17a99655f81dfdafa7f5741c243c
    completed_at: '2026-08-05T20:32:03.200813+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-828
  base_branch: main
  base_sha: da53569a99412c0c8bf2e45f1c0587837a36b444
  head_sha: a5545b61a8db17a99655f81dfdafa7f5741c243c
  submitted_at: '2026-08-05T20:31:23.369024+00:00'
  updated_at: '2026-08-05T20:32:15.326133+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/724
oompah.review_number: '724'
oompah.work_branch: OOMPAH-828
oompah.target_branch: main
oompah.review_head: a5545b61a8db17a99655f81dfdafa7f5741c243c
---
## Summary

Triggered by: OOMPAH-825

Live acceptance failure after deploying OOMPAH-825 on exact main 7978ec91b5532784c5dd6f18bc028954fd3696a9: lifecycle rows OOMPAH-452/453/455/456 are currently Archived and each detail API exposes a completed PASS Archived audit plus an applied Archived result intent, but the v2 lifecycle batch retries them as lifecycle_metadata_not_finalized. Root cause is deterministic: request_archived_audit intentionally fingerprints the mandatory archival disposition via compute_evidence_fingerprint(requirements_text=reason), while _lifecycle_terminal_authorities requires every terminal PASS fingerprint to equal compute_issue_evidence_fingerprint(current issue). Those two canonical domains cannot match, so production-shaped Archived authority is rejected even though its result was already applied. Implementation scope: add target-aware lifecycle finality. For a row whose current state is Archived, accept a completed PASS Archived record only when it is joined to an applied terminal result/retirement intent for the same project/task/audit/attempt/target/fingerprint and the tracker is already Archived; classify the legacy Merged repair row not_needed without any tracker mutation. Do not generalize disposition fingerprints to authorize Done/Merged writes, and continue rejecting incomplete, failed, mismatched, retired, quarantined, or unapplied evidence. Relevant code: archived_audit_requests.py fingerprint contract; terminal_audit_enforcement.py _lifecycle_terminal_authorities and non-Merged recovery; terminal metadata/result-intent schemas. Required tests: production request_archived_audit disposition fingerprint followed by PASS/applied Archived result and current Archived state; all four live-shaped rows converge exactly once with zero status writes; mismatched audit/attempt/fingerprint, applied=false, PASS without applied intent, non-Archived current state, quarantine, restart and retry races remain fail closed. Acceptance: OOMPAH-452/453/455/456 lifecycle rows become completed/not_needed, never mutate tracker status, do not rearm on restart, and lifecycle errors/action_required clear after deployment; focused enforcement/archive/coordinator tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 18:17
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 18:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 18:20
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.4K out [2.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 7s
- Log: OOMPAH-828__20260805T181810Z.jsonl
---
author: oompah
created: 2026-08-05 18:29
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-05 18:29
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-05 18:31
---
## Understanding & Plan

**Root Cause:** Two fingerprinting domains cannot match in terminal_audit_enforcement.py:_lifecycle_terminal_authorities:
- request_archived_audit uses compute_evidence_fingerprint(requirements_text=reason)
- _lifecycle_terminal_authorities requires compute_issue_evidence_fingerprint(current issue)
- Archived authority is rejected despite being already applied

**Implementation Plan:**
1. Add target-aware lifecycle finality check in _lifecycle_terminal_authorities
2. For Archived current state: accept PASS Archived when joined to applied terminal result/retirement intent
3. Match on project/task/audit/attempt/target/fingerprint
4. Classify legacy Merged repair as not_needed without mutation
5. Keep all other reject cases: incomplete, failed, mismatched, retired, quarantined, unapplied

**Relevant Files:**
- terminal_audit_enforcement.py (_lifecycle_terminal_authorities)
- archived_audit_requests.py (fingerprint contract)
- terminal metadata/result-intent schemas

**Verification:** Rows OOMPAH-452/453/455/456 should converge to completed/not_needed with zero status writes
---
author: oompah
created: 2026-08-05 18:37
---
## Discovery

**Root cause confirmed in terminal_audit_enforcement.py:_lifecycle_terminal_authorities**

The function rejects Archived records because:
1. Line 1965: current_fingerprint = compute_issue_evidence_fingerprint(issue, project_id)
2. Line 1975-1978: Filters records where evidence_fingerprint == current_fingerprint
3. But Archived audits use compute_evidence_fingerprint(requirements_text=reason) from archived_audit_requests.py

These fingerprints can never match for disposition-based Archived audits.

**Current logic flow:**
- Line 1711-1714: Lifecycle reconciliation calls _lifecycle_terminal_authorities for Archived rows
- Line 1712-1713: If current_state==ARCHIVED and (passed or overrides), outcome='not_needed'
- Otherwise line 1729: error='lifecycle_metadata_not_finalized'

**Fix location:** Modify _lifecycle_terminal_authorities to add Archived-specific authority check:
- When target_state==ARCHIVED, also check for applied result intents
- Match on audit_id, attempt_id, and joined record
- Accept PASS Archived when result is applied and tracker already Archived
---
author: oompah
created: 2026-08-05 19:42
---
Agent stalled 1 time(s) (4390s (1151 tokens)). Escalating from 'default' to 'deep'. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-05 19:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 115, Tool calls: 54
- Tokens: 926 in / 225 out [1.2K total]
- Cost: $0.0000
- Exit: stalled, Duration: 1h 13m 10s
- Log: OOMPAH-828__20260805T182921Z.jsonl
---
author: oompah
created: 2026-08-05 19:43
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-05 19:43
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-05 20:26
---
## Implementation

Modified oompah/terminal_audit_enforcement.py \`_lifecycle_terminal_authorities\`:

- Added an Archived-target-only branch that accepts a completed PASS Archived audit record when it is joined to an applied Archived result intent via an exact (project_id, task_id, audit_id, attempt_id, target_state, evidence_fingerprint) tuple.
- Fingerprint linkage is exact: record.evidence_fingerprint.digest == attempt.evidence_fingerprint.digest == intent.evidence_fingerprint (digest or {digest: ...}).
- Rejects: quarantined metadata; unapplied intents; retired/superseded intents; cross-task or cross-project intents; non-Archived target intents; missing audit_id/attempt_id fields.
- Never generalizes to Done/Merged: the block is gated on \`target_state == TargetState.ARCHIVED\`.
- Non-mutating: returns the record for the existing \`current_state == ARCHIVED and (passed or overrides)\` → outcome="not_needed" branch. No tracker.update_issue call is added.

Added 10 tests covering the primary case, all failure cases from the acceptance criteria, and a live-shape 4-row (OOMPAH-452/453/455/456) restart-safe convergence test.
---
author: oompah
created: 2026-08-05 20:30
---
## Verification

Focused tests pass:
- tests/test_terminal_audit_enforcement.py: **105 passed** (10 new + 95 existing)
- tests/test_archived_audit_requests.py: 6 passed
- tests/test_terminal_audit.py: 38 passed
- tests/test_terminal_audit_metadata.py: 19 passed
- tests/test_terminal_audit_scanner.py: 15 passed
- tests/test_terminal_fingerprint_canonicalization.py: 10 passed
- tests/test_done_merged_archived_lifecycle.py: 52 passed
- tests/test_terminal_transition_coordinator.py: 187 passed
- tests/test_epic_terminal_audit_contract.py: 20 passed, 1 xfailed
- tests/test_terminal_override.py: 28 passed

Total across neighboring suites: 323 passed, 1 xfailed. Zero regressions.

Rebased cleanly onto origin/main which now contains OOMPAH-829's Done override equivalence work; the Archived-target block sits directly after the existing PASS filter in \`_lifecycle_terminal_authorities\` and is orthogonal to OOMPAH-829's recovered_equivalence logic (that branch runs only when passed==[] and overrides==[] and current_state==DONE).

Head: a5545b61a; branch pushed as origin/OOMPAH-828.
---
author: oompah
created: 2026-08-05 20:31
---
## Completion

Delivered: exact-join Archived-lifecycle finality at head a5545b61a.

- oompah/terminal_audit_enforcement.py: adds target-aware Archived branch in \`_lifecycle_terminal_authorities\`. Accepts a completed PASS Archived record when joined to an applied Archived result intent via exact project/task/audit/attempt/target/fingerprint match. Fails closed on quarantine, unapplied intent, retired/superseded intent, missing ids, cross-target/task/project mismatch, or fingerprint mismatch. Never generalizes disposition fingerprints to Done/Merged writes.
- tests/test_terminal_audit_enforcement.py: adds 10 tests covering the primary case, the four live-shape rows (OOMPAH-452/453/455/456) converging to not_needed with restart safety, and every rejection case from the acceptance criteria.

Effect on OOMPAH-452/453/455/456 lifecycle rows: outcome becomes not_needed, no tracker.update_issue call, no rearm on restart, lifecycle errors/action_required clear once redeployed.
---
author: oompah
created: 2026-08-05 20:31
---
Add target-aware Archived-lifecycle finality: _lifecycle_terminal_authorities now accepts a completed PASS Archived record joined to an applied Archived result intent via an exact project/task/audit/attempt/target/fingerprint tuple, so live rows OOMPAH-452/453/455/456 converge to not_needed with zero tracker mutations while incomplete, failed, mismatched, retired, quarantined, unapplied evidence and Done/Merged targets remain fail-closed. Covered by 10 new tests plus 313 neighboring-suite regressions passing.
---
author: oompah
created: 2026-08-05 20:32
---
Agent completed successfully in 2895s (41200 tokens)
---
author: oompah
created: 2026-08-05 20:32
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/opus]
- Turns: 182, Tool calls: 126
- Tokens: 132 in / 41.1K out [41.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 48m 15s
- Log: OOMPAH-828__20260805T194409Z.jsonl
---
author: oompah
created: 2026-08-05 20:49
---
Branch quality gate passed for `a5545b61a8db17a99655f81dfdafa7f5741c243c` using `make test` in 632.9s. Review creation may proceed.
---
<!-- COMMENTS:END -->
