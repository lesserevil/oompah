---
id: OOMPAH-418
type: epic
status: In Validation
priority: 0
title: Expose oompah's OpenAPI as a streamable MCP server
parent: null
children:
- OOMPAH-419
- OOMPAH-420
- OOMPAH-421
blocked_by: []
labels:
- epic:stale
- ci-fix
assignee: null
created_at: '2026-07-23T19:41:39.116461Z'
updated_at: '2026-07-31T02:09:27.288639Z'
work_branch: epic-OOMPAH-418
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/542
review_number: '542'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/542
oompah.review_number: '542'
oompah.work_branch: epic-OOMPAH-418
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f40f33a428ec
    project_id: proj-14849f1b
    task_id: OOMPAH-418
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 694c4c3fdfdd694922c9b7879727bc7b0048bfa8e8017c38abdd28ac13b67e46
    attempts:
    - version: 1
      attempt_id: attempt-148316224bb3
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 694c4c3fdfdd694922c9b7879727bc7b0048bfa8e8017c38abdd28ac13b67e46
      created_at: '2026-07-31T02:09:15.562257+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T02:09:15.562257+00:00'
      branch_key: epic-OOMPAH-418
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-07-31T02:09:03.971828+00:00'
    updated_at: '2026-07-31T02:09:15.562257+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-148316224bb3
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 694c4c3fdfdd694922c9b7879727bc7b0048bfa8e8017c38abdd28ac13b67e46
    created_at: '2026-07-31T02:09:15.562257+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T02:09:15.562257+00:00'
    branch_key: epic-OOMPAH-418
---
## Summary

Integrate the oapi2mcp OpenAPI-to-MCP gateway pattern into oompah so MCP clients can use oompah's FastAPI OpenAPI contract through a first-party streamable-HTTP MCP endpoint. Scope includes a maintainable gateway module, explicit route and authorization policy for potentially mutating management APIs, server lifecycle integration, dependency packaging, tests, and operator documentation. The endpoint must derive tools from oompah's own OpenAPI schema without requiring a separate oapi2mcp deployment. Acceptance: a configured oompah server exposes a documented MCP endpoint and discovery metadata; allowed MCP calls reach the intended oompah API operations; unsafe or unsupported operations are excluded or denied; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 19:42
---
Created from the operator request to expose oompah's own FastAPI /openapi.json as a first-party streamable MCP server, using the oapi2mcp gateway pattern. Children are sequenced: exposure/security policy (OOMPAH-419), embedded gateway implementation (OOMPAH-420), then integration tests and operator docs (OOMPAH-421).
---
author: oompah
created: 2026-07-23 19:42
---
Epic activated; work begins with OOMPAH-419.
---
author: oompah
created: 2026-07-23 20:33
---
YOLO: CI tests failed on MR #542. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-07-23 20:44
---
YOLO: merged PR #542.
---
author: oompah
created: 2026-07-31 02:09
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-07-31 02:09
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 02:09
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
