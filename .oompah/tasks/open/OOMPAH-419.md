---
id: OOMPAH-419
type: task
status: Open
priority: 1
title: Define the oompah OpenAPI-to-MCP exposure policy
parent: OOMPAH-418
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T19:41:54.055851Z'
updated_at: '2026-07-23T19:43:37.136921Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Design and implement the explicit MCP tool-exposure policy for oompah's generated OpenAPI schema. Determine the mounted endpoint and service-discovery paths, authentication/token propagation behavior, and the allow-list or deny-list for mutating, administrative, credential-bearing, webhook, and restart APIs. Add focused tests proving the generated tool surface includes intended safe operations and excludes or rejects protected operations. Acceptance: the policy is represented in code/configuration, defaults fail closed for protected APIs, and tests cover both allowed and denied operations.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

