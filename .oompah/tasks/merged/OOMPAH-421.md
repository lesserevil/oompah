---
id: OOMPAH-421
type: task
status: Merged
priority: 2
title: Add OpenAPI MCP integration tests and operator documentation
parent: OOMPAH-418
children: []
blocked_by:
- OOMPAH-420
labels: []
assignee: null
created_at: '2026-07-23T19:41:56.160094Z'
updated_at: '2026-07-23T20:46:31.403818Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Add end-to-end and unit coverage for oompah's embedded OpenAPI MCP endpoint: discovery metadata, MCP initialization/tool listing, allowed tool invocation, protected-operation denial, and graceful behavior when the optional MCP dependency is unavailable. Document enablement/configuration, endpoint URLs, authentication expectations, and verification steps in docs/. Acceptance: tests use existing Makefile test conventions, documentation gives an operator a complete setup and verification path, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

