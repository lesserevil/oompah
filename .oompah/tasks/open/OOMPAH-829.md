---
id: OOMPAH-829
type: bug
status: Open
priority: 1
title: Migrate legacy equivalent Done-override fingerprints for structural maintenance
  tasks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T13:24:24.014858Z'
updated_at: '2026-08-05T18:18:29.017667Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1551768186f6e7b315b12d3550594c1936f9f224777cfb8422e99a4316fd63d5
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 68e7da61-d250-43d3-adfb-19184b1cb7e3
  claim_owner: 3a62b7a5-bbb7-4494-ae8d-738d99774e0d
  claimed_at: '2026-08-05T18:18:03.139523+00:00'
  claim_expires_at: '2026-08-05T18:48:03.139523+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3f9f6276-7026-48e1-aecb-1525456b35a5
---
## Summary

Triggered by: OOMPAH-825

Live acceptance failure after deploying OOMPAH-825 on exact main 7978ec91b5532784c5dd6f18bc028954fd3696a9: OOMPAH-662 repaired from Merged to Done, but OOMPAH-660 remains Merged with lifecycle_repair_not_applied. OOMPAH-660 is the original OOMPAH-663 fingerprint-canonicalization reproduction. Its current integrated issue fingerprint and original integration-staged Done audit are ab40139d2035 at exact integrated SHA 793bcc7969d39634dab560ed0a10b9dcad7a9716, while its applied authorized Done override and duplicate no-auditor request carry legacy normalized/API fingerprint 62954f9b5fdc. OOMPAH-825's live-shaped test incorrectly modeled the override as already equal to the current fingerprint, so the promised 660 repair cannot occur. Implementation scope: add a bounded, explicit legacy-equivalence migration for structurally Done-only direct epic maintenance rows. Reconstruct both known canonical snapshot shapes from durable integration metadata (integration-staged integrated base/head/contributor shape and legacy normalized API/work-branch shape); accept an applied Done override only when its digest equals one reconstructed shape, the current digest equals the other, exact project/task/target/authorized/applied fields match, immutable integrated SHA/branch evidence is unchanged, current state is Merged, and the Merged validator still rejects it as Done-only under the project lock. Persist the equivalence/migration version before the one Done write, then retire only the exact child's incompatible Merged metadata. Never accept arbitrary fingerprint drift, comment/reason text, missing integration evidence, CI-fix/merge-conflict tasks, retired/superseded overrides, or SCM outage. Relevant code: terminal_audit.py canonical fingerprint variants/history from OOMPAH-663; terminal_audit_enforcement.py lifecycle authority and locked repair; live OOMPAH-660 metadata. Required tests: exact production-shaped OOMPAH-660 ab401↔62954 pair repairs once; OOMPAH-662 current-match control; one-field changes to integrated SHA, base branch, task identity, target, override authority/application, or structural classification fail closed; restart/crash intent recovery and cross-project isolation. Acceptance: OOMPAH-660 alone moves Merged to Done exactly once without manual task/ledger edits, row completes/reconciled and stays idempotent, unrelated historical overrides remain rejected, lifecycle warning converges clear, focused fingerprint/enforcement/coordinator tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 18:18
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-08-05 18:18
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
