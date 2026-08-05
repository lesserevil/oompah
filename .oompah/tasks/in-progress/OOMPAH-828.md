---
id: OOMPAH-828
type: bug
status: In Progress
priority: 1
title: Treat applied Archived audit results as final lifecycle no-ops
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T13:24:20.492002Z'
updated_at: '2026-08-05T18:31:28.503416Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
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
oompah.agent_run_id: fc4ba568-649e-416d-89ec-5af3967a1b63
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2369
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2369
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2369
    cost_usd: 0.0
    recorded_at: '2026-08-05T18:20:05.407374+00:00'
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
<!-- COMMENTS:END -->
