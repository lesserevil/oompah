---
id: OOMPAH-504
type: feature
status: In Progress
priority: 1
title: Compact agent prompt history around actionable handoffs
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:06:00.486812Z'
updated_at: '2026-07-28T17:44:26.501191Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 1462c7f5-6d20-40e0-9bbb-f21fe5d2a245
oompah.work_branch: epic-OOMPAH-502
---
## Summary

Problem: every dispatch injects every prior task comment into WORKFLOW.md. Multi-focus tasks accumulate long progress, test, and completion comments, forcing each fresh agent to replay stale context and increasing provider latency/tokens.

Implementation: add a deterministic prompt-comment compactor before render_prompt. Always retain the newest human-authored instruction/question, the latest Focus handoff comment, Needs Human instructions when present, and the most recent comments within configurable count and byte budgets. Insert a trusted omission notice with omitted count and tell the agent to use oompah task view for full history. Preserve chronological order, author/timestamp metadata, untrusted-content provenance wrapping, mid-run comment delivery, and the full canonical tracker history. Add OOMPAH_PROMPT_MAX_COMMENTS and OOMPAH_PROMPT_MAX_COMMENT_BYTES to .env.example with conservative defaults; do not put tunables in WORKFLOW.md.

Tests: add unit tests for retention priority, ordering, deduplication, byte/count limits, enormous single comments, all-human histories, latest handoff outside the recent window, Needs Human final questions, and prompt-injection delimiters. Add orchestrator integration tests proving only compacted comments reach render_prompt while tracker storage is untouched.

Acceptance criteria: prompt size is bounded; no latest actionable human request or focus handoff is lost; full history remains retrievable; provenance/security tests and focused tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:06
---
Claimed for manual implementation by the current Codex session. Held in Backlog while the shared epic branch is built so Oompah does not dispatch another agent; status will move to In Progress and Done as this session completes the slice.
---
author: oompah
created: 2026-07-28 15:12
---
Implementing a pure, non-mutating comment compactor at the three initial-prompt paths. It will retain latest human context, latest Focus handoff, the final Needs Human instruction, and recent comments within count/byte caps; a renderer-only trusted omission notice will point agents to the full task history.
---
author: oompah
created: 2026-07-28 15:16
---
Implemented and pushed in commit 85be456eb. Fresh agent prompts now compact comment history without mutating tracker storage, retain prioritized human/handoff/Needs Human context plus recent comments, include a trusted full-history notice, preserve untrusted provenance, and support environment-only count/byte caps. Focused prompt/config/provenance suite: 439 passed.
---
author: oompah
created: 2026-07-28 15:16
---
Startup task history is bounded and actionable context is retained; canonical tracker history and provenance remain intact.
---
author: oompah
created: 2026-07-28 17:44
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 17:44
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
