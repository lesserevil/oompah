---
id: OOMPAH-504
type: feature
status: Backlog
priority: 1
title: Compact agent prompt history around actionable handoffs
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:06:00.486812Z'
updated_at: '2026-07-28T15:06:00.486812Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem: every dispatch injects every prior task comment into WORKFLOW.md. Multi-focus tasks accumulate long progress, test, and completion comments, forcing each fresh agent to replay stale context and increasing provider latency/tokens.

Implementation: add a deterministic prompt-comment compactor before render_prompt. Always retain the newest human-authored instruction/question, the latest Focus handoff comment, Needs Human instructions when present, and the most recent comments within configurable count and byte budgets. Insert a trusted omission notice with omitted count and tell the agent to use oompah task view for full history. Preserve chronological order, author/timestamp metadata, untrusted-content provenance wrapping, mid-run comment delivery, and the full canonical tracker history. Add OOMPAH_PROMPT_MAX_COMMENTS and OOMPAH_PROMPT_MAX_COMMENT_BYTES to .env.example with conservative defaults; do not put tunables in WORKFLOW.md.

Tests: add unit tests for retention priority, ordering, deduplication, byte/count limits, enormous single comments, all-human histories, latest handoff outside the recent window, Needs Human final questions, and prompt-injection delimiters. Add orchestrator integration tests proving only compacted comments reach render_prompt while tracker storage is untouched.

Acceptance criteria: prompt size is bounded; no latest actionable human request or focus handoff is lost; full history remains retrievable; provenance/security tests and focused tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

