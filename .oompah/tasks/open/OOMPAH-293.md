---
id: OOMPAH-293
type: epic
status: Open
priority: 1
title: Build Git-backed repository maps for faster agent startup
parent: null
children:
- OOMPAH-294
- OOMPAH-295
- OOMPAH-296
- OOMPAH-297
- OOMPAH-298
- OOMPAH-299
- OOMPAH-300
blocked_by: []
labels:
- needs:backend
- needs:agents
assignee: null
created_at: '2026-07-21T15:13:33.130186Z'
updated_at: '2026-07-21T15:45:14.485944Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implement an Oompah-native repository-map capability inspired by Aider’s RepoMap design. It must parse supported source repositories with Tree-sitter, rank symbols and file relationships into a compact context map, persist deterministic artifacts keyed by the analyzed Git commit, and inject only a task-relevant, token-budgeted slice into agent startup prompts. The feature must require no external service or database and must not treat repository text as trusted instructions.\n\nScope:\n- Define the artifact schema, lifecycle, invalidation, and Git-backed storage on the Oompah state branch.\n- Add Tree-sitter-based indexing and an Aider-style definition/reference ranking algorithm.\n- Select task-relevant map slices from task metadata, changed files, and repository relationships.\n- Integrate the slice into all agent focus prompts with explicit untrusted-data boundaries.\n- Provide observability, operator controls, bootstrap support, migration behavior, documentation, and end-to-end tests.\n\nOut of scope: vector embeddings, an external graph database, a long-running index service, and source-code modification by the indexer.\n\nDone when a newly assigned agent receives a bounded, current map for its checkout; stale maps are not used; index failures degrade safely to the existing startup behavior; and all managed projects can enable the feature without changing their application code.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

