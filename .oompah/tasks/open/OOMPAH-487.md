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
labels: []
assignee: null
created_at: '2026-07-28T13:08:26.170630Z'
updated_at: '2026-07-28T18:07:12.533089Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

