---
id: OOMPAH-295
type: task
status: Backlog
priority: 1
title: Add Tree-sitter repository symbol and reference extraction
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-294
labels: []
assignee: null
created_at: '2026-07-21T15:13:48.374539Z'
updated_at: '2026-07-21T15:14:19.841547Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implement a standalone repository indexer that walks a checked-out repository, respects existing ignore rules, and uses Tree-sitter Python bindings plus packaged grammars to extract file-level symbols and references. Start with the languages used by Oompah-managed projects: Python, Rust, TypeScript/JavaScript, YAML, and Markdown where useful. Record normalized relative paths, symbol name, kind, line span, and reference names using the artifact contract from OOMPAH-294. Handle parse errors and unsupported file types without failing the repository scan.\n\nDo not rank results, persist artifacts, or change prompts in this task. Do not execute project code.\n\nTests:\n- Fixture repositories for each supported language verify expected extracted symbols and references.\n- Verify ignored, binary, oversized, and unsupported files are skipped with recorded diagnostics.\n- Verify malformed source yields partial results and no crash.\n\nAcceptance criteria:\n- The indexer runs solely on checked-out file content and requires no project build.\n- Supported-language output conforms to the repository-map artifact types.\n- Unsupported or invalid input degrades safely and is observable.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

