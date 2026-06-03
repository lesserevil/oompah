---
id: TASK-404.1
title: Make credential warning identify provider context
status: Done
assignee: []
created_date: '2026-06-03 00:37'
updated_date: '2026-06-03 00:47'
labels:
  - bug
  - provider
dependencies: []
parent_task_id: TASK-404
priority: high
ordinal: 62000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The dashboard credential banner currently says only 'Missing provider credentials for TASK-...' and tells the operator to check API key configuration. That is not actionable when multiple projects, profiles, roles, and providers are configured. Improve credential-error alerts so they include safe, non-secret context: project name/id when known, agent profile, model role, provider/model when known, and candidate providers/models when only a role can be inferred. Never include raw api_key/token values.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Credential-error alert messages include the affected task identifier and attempt number as before.
- [ ] #2 When retry context has exact provider/model/profile data from the failed run, the alert includes those names.
- [ ] #3 When exact provider/model data is unavailable, the alert derives and includes likely project/profile/role/provider candidate names where possible.
- [ ] #4 Alert payloads include structured context fields useful for UI/API debugging, without secrets.
- [ ] #5 Alert messages never include raw api_key, token, or Authorization values from the original error string.
- [ ] #6 Tests cover exact retry context, derived role candidates, missing-context fallback, and secret redaction.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented actionable credential retry alerts. Retry state now keeps safe project/profile/role/provider/model/candidate metadata, credential alerts include structured non-secret context plus exact or derived provider details, and missing_credentials preflight failures are detected. Verified with focused credential alert tests and full make test.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Run focused credential alert tests.
- [ ] #2 Run make test before closing.
<!-- DOD:END -->
