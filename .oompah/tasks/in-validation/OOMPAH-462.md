---
id: OOMPAH-462
type: feature
status: In Validation
priority: 1
title: Define terminal-audit records, enums, and evidence fingerprints
parent: OOMPAH-457
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:05:04.307001Z'
updated_at: '2026-08-04T21:40:22.724959Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 78ab4991-6121-4786-9fc3-6b6219cca49b
oompah.work_branch: epic-OOMPAH-457
oompah.task_costs:
  total_input_tokens: 282
  total_output_tokens: 7385
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 282
      output_tokens: 7385
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 282
    output_tokens: 7385
    cost_usd: 0.0
    recorded_at: '2026-07-28T18:26:59.093848+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-6b9006f15a83
    project_id: proj-14849f1b
    task_id: OOMPAH-462
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4938a2872c71425da5737f22cb3f00bacdfc4b570002961834975899f6070517
    attempts:
    - version: 1
      attempt_id: attempt-a986b910cb52
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 4938a2872c71425da5737f22cb3f00bacdfc4b570002961834975899f6070517
      created_at: '2026-08-04T21:40:16.673744+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:40:16.673744+00:00'
      branch_key: epic-OOMPAH-457
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T21:33:26.272147+00:00'
    updated_at: '2026-08-04T21:40:16.673744+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-a986b910cb52
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4938a2872c71425da5737f22cb3f00bacdfc4b570002961834975899f6070517
    created_at: '2026-08-04T21:40:16.673744+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:40:16.673744+00:00'
    branch_key: epic-OOMPAH-457
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
author: oompah
created: 2026-07-28 18:26
---
Focus handoff: duplicate_detector

**Outcome**: No duplicate found. OOMPAH-462 is a unique, original feature task.

**Investigation Details**:
- Searched all .oompah/tasks directories (200+ tasks) and docs/plans for terminal-audit, audit records, evidence fingerprints, verdict, contributor identity concepts
- Source code review: no existing Audit/Record/Fingerprint/Evidence domain classes in oompah/ or src/
- Git history: no references to terminal-audit infrastructure or prior attempts
- Examined existing dataclass patterns in oompah/models.py (EpicRebaseStateEntry, SharedAbsorptionEvidence, etc.) for implementation reference

**Context & Related Tasks**:
- Parent epic: OOMPAH-457 (Build the terminal-audit state model and transition coordinator) — defines the overall state machine foundation
- Sibling OOMPAH-461 (Done): Added In Validation status — orthogonal scope, already completed
- Next sibling tasks OOMPAH-463..467: Will consume the domain models defined in this task

**Files & patterns to follow**:
- oompah/models.py: Pattern for versioned to_dict/from_dict (see EpicRebaseStateEntry lines 56–95, SharedAbsorptionEvidence lines 116–153)
- tests/test_models.py: Existing dataclass test patterns
- oompah/statuses.py: Enum patterns (see EpicRebaseState enum lines 32–54)

**Implementation Scope** (from task):
- New terminal_audit domain module with typed enums/dataclasses
- Enums: TargetState (Done, Merged, Archived), RequestState, Verdict, FailureClassification
- Records: ContributorIdentity, EvidenceFingerprint, AuditAttempt, TerminalAuditRecord
- Deterministic SHA-256 fingerprint from normalized: requirements text, project/task identity, source/target branch names/SHAs, review identity/state, child-audit digest, contributor identities (order-independent)
- Never include: credentials, full diffs, model prose
- Versioned to_dict/from_dict with strict required-field validation, forward-compatible optional fields
- Tests: deterministic hashing, order-independent inputs, changed evidence producing new fingerprint, malformed enum rejection, legacy missing optional fields

**Acceptance Criteria**:
- Other tasks can construct, persist, compare without tracker-specific logic
- Identical evidence → same fingerprint
- Material evidence change → different fingerprint

**Recommended next focus**: feature
---
author: oompah
created: 2026-07-28 18:26
---
Agent completed successfully in 124s (7667 tokens)
---
author: oompah
created: 2026-07-28 18:27
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 77, Tool calls: 39
- Tokens: 282 in / 7.4K out [7.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 4s
- Log: OOMPAH-462__20260728T182459Z.jsonl
---
author: oompah
created: 2026-07-28 18:27
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 18:27
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:27
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-28 18:27
---
Understanding: I will add a standalone terminal-audit domain module with typed enums, versioned dataclasses, strict required-field decoding, optional-field compatibility, and deterministic SHA-256 evidence fingerprints. I will first inspect existing models, enum, serialization, and test conventions, then implement focused tests and run the prescribed checks.
---
author: oompah
created: 2026-07-28 18:27
---
Discovery: No terminal-audit implementation exists. Existing models.py uses dataclass to_dict/from_dict, while statuses.py defines Done, Merged, and Archived. The new module will be tracker-independent and will enforce its own schema/version and enum validation.
---
author: oompah
created: 2026-07-28 18:34
---
Implementation: Added oompah/terminal_audit.py with TargetState, RequestState, Verdict, FailureClassification, ContributorIdentity, EvidenceFingerprint, AuditAttempt, and TerminalAuditRecord. Serialization is versioned and strict for required fields/enums while ignoring unknown future keys; fingerprinting uses normalized labeled JSON evidence, SHA-256, and sorted contributors/child digests. Added tests/test_terminal_audit.py covering round trips, legacy optionals, malformed input, deterministic order-independent hashing, and material evidence changes.
---
author: oompah
created: 2026-07-28 18:34
---
Verification: Focused terminal-audit, models, and SCM suites pass: 346 passed. git diff --check is clean. The standalone fingerprint tests cover deterministic serialization/hashing, order-independent contributors and child audits, changed requirements/project/task/branches/SHAs/review/children, strict versions/enums/required fields, and legacy optional fields.
---
author: oompah
created: 2026-07-28 18:37
---
Verification update: make test could not initialize because the astral-uv launcher fails in this environment with a DBus transient-scope error. Reproducing the Makefile pytest invocation with the required OOMPAH_PYTEST_RUN_ROOT set completed successfully: 12,659 passed, 7 skipped (14 pre-existing warnings).
---
author: oompah
created: 2026-07-28 18:38
---
Completion: Delivered and pushed commit 7325be61a. The tracker-neutral terminal-audit module provides versioned typed records/enums, strict decoding with optional-field compatibility, and deterministic SHA-256 evidence fingerprints over normalized permitted evidence with order-independent contributors/children. Focused tests, full equivalent pytest gate, and secret scan pass; branch is up to date with origin.
---
author: oompah
created: 2026-07-28 18:39
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 54
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 12m 10s
- Log: OOMPAH-462__20260728T182710Z.jsonl
---
author: oompah
created: 2026-07-28 18:39
---
Added tracker-neutral terminal-audit enums and versioned records with strict serialization and deterministic SHA-256 evidence fingerprints; tests and full equivalent gate pass.
---
author: oompah
created: 2026-08-04 21:33
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
