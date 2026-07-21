---
id: OOMPAH-298
type: task
status: Open
priority: 1
title: Inject task-relevant repository maps into agent focus startup prompts
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-296
- OOMPAH-297
labels: []
assignee: null
created_at: '2026-07-21T15:14:08.542161Z'
updated_at: '2026-07-21T15:45:18.458988Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Integrate repository maps into the agent prompt assembly path. Resolve the agent checkout commit, load only a fresh matching artifact, derive seeds from the task title, description, linked files, PR/commit data, and focus handoff, then render a token-budgeted map with OOMPAH-296. Insert it into every focus startup prompt in a clearly labeled untrusted repository-context block. Preserve the existing prompt when no fresh map is available. Do not expose data from another project, branch, or commit.\n\nTests:\n- Prompt tests verify a fresh matching map is included for each focus type.\n- Verify stale SHA, wrong project, missing artifact, and rendering failure omit the map and retain normal startup.\n- Verify the configured token ceiling is respected and task-specific seeds affect selection.\n- Verify the prompt labels repository text as data, not instructions, and cannot override system/task instructions.\n\nAcceptance criteria:\n- Newly started agents receive a bounded, relevant map without needing extra model round trips.\n- No startup is blocked by map generation or retrieval failure.\n- Prompt provenance and SHA are available in agent diagnostics.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

