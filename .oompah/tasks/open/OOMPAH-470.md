---
id: OOMPAH-470
type: feature
status: Open
priority: 1
title: Seed the auditor role and select an independent provider-model candidate
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-468
- OOMPAH-457
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:06:10.311921Z'
updated_at: '2026-07-28T22:52:33.920839Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e2241edb48d51aa19dd51c349cf33ea284834053394f0393dcce2d7d457837e5
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: c9cb0ce0-87f1-4083-9699-75dac50d5fcc
  claim_owner: 8e692a0c-71f6-4607-8341-3faedd0fb344
  claimed_at: '2026-07-28T22:50:43.516111+00:00'
  claim_expires_at: '2026-07-28T23:20:43.516111+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 83504f82-e263-4c6c-8e64-478cadd66d06
oompah.work_branch: epic-OOMPAH-458
---
## Summary

Implementation scope

Create a reserved editable auditor role. On migration, seed it from the deduplicated union of deep, standard, and default role candidates, followed by remaining configured provider defaults; do not hardcode local provider IDs. Implement candidate filtering that first respects project provider whitelist, credentials, health, budget, and model validity, then excludes every contributor model. Prefer a provider not used by any contributor. Fall back to a contributing provider only when its candidate has an explicit model ID different from every contributed model on that provider. An SDK-managed unknown model on a contributing provider is not independently provable and must be excluded. Return normalized no-candidate reasons.

Tests

Cover different provider/model, same-provider different model fallback, same model on another provider, multi-contributor epic exclusion, unknown ACP models, round-robin ordering, whitelist, unhealthy/missing credentials, budget, empty role, migration seeding, and no-candidate diagnostics. Run focused tests and make test.

Acceptance criteria

Selected auditors are demonstrably independent under the agreed policy; unsafe or unverifiable candidates are never used; operators can edit auditor candidates through the existing role configuration path.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 22:17
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-28 22:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 22:17
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 17s
- Log: OOMPAH-470__20260728T221720Z.jsonl
---
author: oompah
created: 2026-07-28 22:50
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-28 22:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 22:52
---
Focus handoff: duplicate_detector

**Duplicate preflight verdict: no_duplicate**

**Matches: none**

**Evidence:**
Searched `.oompah/tasks/` (open, backlog, archived, merged), git history, codebase patterns, and design docs for related work on:
- auditor role creation/seeding
- independent provider-model candidate selection
- contributor model exclusion
- role candidate filtering by whitelist/credentials/health/budget

Results:
- No existing tasks or implementations of an 'auditor' role candidate selector
- OOMPAH-468 (already merged) established WorkContributor tracking; OOMPAH-457 (already merged) stabilized checkpoint coalescing; neither implement auditor role selection
- Terminal audit infrastructure exists (test_terminal_audit.py, terminal_audit.py) but is separate from provider/model role selection
- RoleStore/Candidate classes (oompah/roles.py) exist for standard roles (fast/standard/deep/default) but lack auditor role or independent-candidate filtering
- No design docs or code for 'exclude contributors', 'prefer independent provider', or 'seed from deduplicated union' logic

**Closest reviewed tasks (all unrelated):**
- OOMPAH-311: detect independently-merged epic children (different concept)
- TASK-407.7: role candidate UI (covers matrix editor, not auditor role logic)
- OOMPAH-468: contributor provenance tracking (prerequisite, not implementation)

**Conclusion:** OOMPAH-470 is a fresh feature. The blocking dependencies (OOMPAH-468, OOMPAH-457) are complete and unblocking work can proceed.
---
<!-- COMMENTS:END -->
