---
id: OOMPAH-297
type: task
status: Open
priority: 1
title: Generate and maintain repository maps on Git-backed state branches
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-294
- OOMPAH-296
labels: []
assignee: null
created_at: '2026-07-21T15:14:07.528667Z'
updated_at: '2026-07-21T15:45:17.612801Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Connect repository-map generation to Oompah project synchronization. For a managed project checkout, reuse a fresh artifact for the exact target commit or generate one from the Tree-sitter extractor and ranked renderer. Write it atomically to the configured project state branch using the lifecycle from OOMPAH-294; never write generated map files to the managed repository main or release branches. Coalesce duplicate requests for the same project/SHA and retain only the configured bounded history.\n\nGeneration must run as a bounded background operation. A failed, stale, or partial index must be reported and must not block normal task dispatch.\n\nTests:\n- Integration tests with a temporary Git remote prove maps land only on the state branch.\n- Verify same-SHA requests reuse the artifact and changed-SHA requests regenerate it.\n- Verify concurrent requests coalesce and atomic writes never expose partial JSON.\n- Verify failures/timeouts leave task dispatch usable and emit a diagnostic state.\n\nAcceptance criteria:\n- One fresh artifact is available per successfully indexed project commit.\n- No repository code branch receives index-only commits.\n- Storage retention and failure behavior match the design document.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

