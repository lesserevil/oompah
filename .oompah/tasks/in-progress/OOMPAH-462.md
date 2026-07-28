---
id: OOMPAH-462
type: feature
status: In Progress
priority: 1
title: Define terminal-audit records, enums, and evidence fingerprints
parent: OOMPAH-457
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:05:04.307001Z'
updated_at: '2026-07-28T18:26:39.019125Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 34e4d1c3-3dbe-4d98-9818-f069adab7b1f
oompah.work_branch: epic-OOMPAH-457
---
## Summary

Implementation scope

Create a small terminal-audit domain module with typed enums/dataclasses for target state (Done, Merged, Archived), request state, verdict, failure classification, contributor identity, evidence fingerprint, and audit attempt. Define versioned to_dict/from_dict methods with strict required-field validation and forward-compatible optional fields. Build a deterministic SHA-256 evidence fingerprint from normalized requirements text, project/task identity, source and target branch names/SHAs, review identity/state, child-audit digest, and contributor identities. Never include credentials, full diffs, or model prose in the fingerprint payload.

Tests

Test deterministic serialization and hashing, order-independent contributor/child input, changed requirements/SHA/review/children producing a new fingerprint, malformed/unknown enum rejection, and legacy missing optional fields. Run focused tests and make test.

Acceptance criteria

Other tasks can construct, persist, and compare terminal-audit records without tracker-specific logic; identical evidence produces the same fingerprint and every material evidence change produces a different one.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:24
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 18:26
---
Duplicate screening complete: OOMPAH-462 is NOT a duplicate.

Investigation scope:
- All .oompah/tasks directories (archived, merged, open, backlog) searched for keywords: terminal-audit, audit-record, evidence fingerprint, fingerprint, audit, verdict, target state, contributor identity
- Source code search (oompah/ and src/) for existing Audit/Record/Fingerprint/Evidence classes — none found
- Plans and docs directories searched for audit record design discussions — none found  
- Git history searched for terminal-audit, OOMPAH-462, OOMPAH-457 references
- Reviewed 25+ related tasks covering state models, dataclasses, serialization patterns

Key findings:
- OOMPAH-462 is a child task of epic OOMPAH-457 (Build the terminal-audit state model and transition coordinator)
- OOMPAH-461 (sibling) completed the canonical In Validation status work — distinct scope
- Existing fingerprinting references are unrelated (dashboard reconciliation [OOMPAH-205], GitHub intake dedup [OOMPAH-118])
- SharedAbsorptionEvidence dataclass [OOMPAH-219] is for shared-worktree commit absorption, not terminal audits
- No existing terminal-audit domain infrastructure in codebase

Closest reviewed candidates (NOT duplicates):
1. OOMPAH-219 (Archived): SharedAbsorptionEvidence dataclass pattern — different domain (worktree absorption, not terminal audits)
2. OOMPAH-461 (Done): In Validation status — completed, orthogonal scope (status constant, not audit records)
3. OOMPAH-205 (Archived): Dashboard board fingerprinting — UI optimization, not audit domain

Conclusion: OOMPAH-462 is a unique, original feature implementation task. No prior implementation or duplicate found.
---
<!-- COMMENTS:END -->
