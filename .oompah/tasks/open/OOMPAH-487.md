---
id: OOMPAH-487
type: feature
status: Open
priority: 1
title: Document auditor configuration, overrides, migration, and recovery
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-483
- OOMPAH-486
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:08:26.170630Z'
updated_at: '2026-07-29T02:08:10.368290Z'
work_branch: epic-OOMPAH-460
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e6e3f14cf037c045da64b0f3e5b5bb7d31ae4e132ba23991152738e863c246a9
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4fc2b198-a0c2-41e9-b7bc-ef215c55ba05
  claim_owner: 5d80b10c-0ace-4fc9-8e33-587cf319fe4d
  claimed_at: '2026-07-29T02:08:06.413988+00:00'
  claim_expires_at: '2026-07-29T02:38:06.413988+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 750a01b5-18bb-4d1e-b8ef-9ae288a4374a
oompah.work_branch: epic-OOMPAH-460
---
## Summary

Implementation scope

Add OOMPAH_AUDIT_MAX_ATTEMPTS to .env.example and ServiceConfig using existing parsing conventions. Document the auditor role, independence rules, project whitelist effects, each target-specific audit, In Validation, failure routing, explicit owner override, no-candidate recovery, upgrade grandfathering, and restart behavior in docs/. Update status/workflow references and CLI help examples. Deprecate OOMPAH_VERIFY_COMPLETION and OOMPAH_VERIFY_COMPLETION_LLM with startup warnings and a release-note migration entry; retain parsing for one compatibility release but do not let them disable mandatory audits. Use Mermaid for any lifecycle diagram.

Tests

Add config/default/env parsing tests, deprecation-warning tests, documentation link/content checks, .env.example coverage, and examples that match actual CLI/API flags. Run focused tests and make test.

Acceptance criteria

A junior operator can configure at least two independent auditor candidates, diagnose Needs Human due to no candidate, execute an owner override, and understand upgrade behavior using only public docs.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 02:08
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
