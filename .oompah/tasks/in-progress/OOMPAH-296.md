---
id: OOMPAH-296
type: task
status: In Progress
priority: 2
title: Implement Aider-style repository-map ranking and bounded rendering
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-295
labels: []
assignee: null
created_at: '2026-07-21T15:13:49.289592Z'
updated_at: '2026-07-21T16:40:19.274200Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5d351f24-3944-4dd2-b76d-f0fe6656d07a
---
## Summary

Build the ranking and rendering layer over extracted Tree-sitter tags. Following Aider RepoMap principles, form a directed relationship graph from definitions and references, rank important symbols/files, and render a stable, compact textual map within a caller-provided token budget. Prefer task-mentioned identifiers and seed files when supplied; include useful definitions rather than raw source bodies. Ensure ties sort deterministically.\n\nDo not persist maps or alter agent prompts in this task.\n\nTests:\n- Synthetic graph fixtures verify referenced symbols outrank isolated symbols.\n- Verify task-mentioned names and seed files receive the documented boost.\n- Verify output never exceeds the requested token budget, remains deterministic, and remains readable when no edges exist.\n- Verify paths and source excerpts are escaped/marked as untrusted data.\n\nAcceptance criteria:\n- Callers can request a bounded text map from an extracted artifact.\n- Results prioritize structurally relevant and task-relevant code.\n- Rendering has no network dependency and does not expose files outside the repository.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 16:40
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:40
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
