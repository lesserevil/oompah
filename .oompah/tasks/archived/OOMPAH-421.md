---
id: OOMPAH-421
type: task
status: Archived
priority: 2
title: Add OpenAPI MCP integration tests and operator documentation
parent: OOMPAH-418
children: []
blocked_by:
- OOMPAH-420
labels: []
assignee: null
created_at: '2026-07-23T19:41:56.160094Z'
updated_at: '2026-07-30T21:17:49.680294Z'
work_branch: epic-OOMPAH-418--task-OOMPAH-421
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-40261aad3d68: '2026-07-30T21:17:47.525695+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-6c7704f8ae1b
    project_id: proj-14849f1b
    task_id: OOMPAH-421
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f5666d57de9c139ece73c55f95eb70e1cc75fc073055a234b49cd26d6e5534db
    attempts:
    - version: 1
      attempt_id: attempt-40261aad3d68
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f5666d57de9c139ece73c55f95eb70e1cc75fc073055a234b49cd26d6e5534db
      created_at: '2026-07-30T20:55:00.393644+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T20:55:00.393644+00:00'
      branch_key: OOMPAH-421
      verdict: pass
      completed_at: '2026-07-30T21:17:47.525540+00:00'
      ended_at: '2026-07-30T21:17:47.525540+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-07-30T20:54:51.046670+00:00'
    updated_at: '2026-07-30T21:17:47.525540+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-40261aad3d68
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f5666d57de9c139ece73c55f95eb70e1cc75fc073055a234b49cd26d6e5534db
    created_at: '2026-07-30T20:55:00.393644+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T20:55:00.393644+00:00'
    branch_key: OOMPAH-421
oompah.work_branch: epic-OOMPAH-418--task-OOMPAH-421
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-418--task-OOMPAH-421
  base_branch: epic-OOMPAH-418
  base_sha: c048ba706cbe9b1342b80a67576a49b82887e84a
  updated_at: '2026-07-30T20:55:05.394483+00:00'
---
## Summary

Add end-to-end and unit coverage for oompah's embedded OpenAPI MCP endpoint: discovery metadata, MCP initialization/tool listing, allowed tool invocation, protected-operation denial, and graceful behavior when the optional MCP dependency is unavailable. Document enablement/configuration, endpoint URLs, authentication expectations, and verification steps in docs/. Acceptance: tests use existing Makefile test conventions, documentation gives an operator a complete setup and verification path, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 20:54
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-07-30 20:55
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 20:55
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 21:17
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- previous_state_confirmed: Merged (state-branch commit a162973a3 renamed .oompah/tasks/open/OOMPAH-421.md -> .oompah/tasks/merged/OOMPAH-421.md; audit chain lists previous_state: Merged)
- pending_audit_id: audit-6c7704f8ae1b (matches trusted scheduler metadata)
- requested_target: Archived (from Aged Merged auto-archive queued 2026-07-30 20:54)
- epic_merge_commit: 10fac3f6e Merge pull request #542 from lesserevil/epic-OOMPAH-418 (into origin/main)
- integration_tests_present: tests/test_mcp_gateway.py: 14 test functions covering discovery, auth, transport security, init/list/call, and dispatch helpers
- unit_test_neighbor: tests/test_mcp_exposure_policy.py present with policy classification tests (SAFE_READ, TASK_MUTATION allowed; ORCHESTRATOR_CONTROL/WEBHOOK_INGESTION/CREDENTIAL_BEARING/ADMIN_MUTATION/RELEASE_DELIVERY denied)
- operator_docs_present: docs/authentication.md § MCP Gateway (lines 442-468) documents /.well-known/mcp discovery, /api/mcp/v1 endpoint, HTTPS/Basic-auth expectations, and client configuration snippet with password-file reference
- design_doc_reference: plans/mcp-openapi-exposure-policy.md line 5 records: 'Integration tests + docs: OOMPAH-421'
- children_blocked: children: [] (no dependents waiting on this task)
- task_metadata_source: state branch oompah/state/proj-14849f1b @ commit 09f8ea65d shows task file with pending_chain audit-6c7704f8ae1b, target_state=Archived, evidence_fingerprint digest=f5666d57de9c139ece73c55f95eb70e1cc75fc073055a234b49cd26d6e5534db (matches trusted contract)
---
<!-- COMMENTS:END -->
