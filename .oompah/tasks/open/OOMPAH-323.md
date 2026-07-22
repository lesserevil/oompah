---
id: OOMPAH-323
type: task
status: Open
priority: 1
title: Implement GitLab Issues tracker with Oompah status governance
parent: OOMPAH-318
children:
- OOMPAH-337
- OOMPAH-338
- OOMPAH-339
- OOMPAH-343
- OOMPAH-347
- OOMPAH-354
blocked_by:
- OOMPAH-319
labels:
- focus-complete:duplicate_detector
- focus-complete:epic_planner
- needs:feature
- epic:rebasing
assignee: null
created_at: '2026-07-21T20:34:25.248230Z'
updated_at: '2026-07-22T04:00:44.935403Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e6a1afd4-99af-49ed-9528-28654633cfed
oompah.task_costs:
  total_input_tokens: 190131
  total_output_tokens: 7408
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 190131
      output_tokens: 7408
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 190106
    output_tokens: 1613
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:04:27.163693+00:00'
  - profile: standard
    model: unknown
    input_tokens: 25
    output_tokens: 5795
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:06:58.184823+00:00'
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, GitLab implementation.

Add GitLabIssueTracker implementing every TrackerProtocol operation through GitLab Issues, notes, labels, and issue links. Use oompah:status:* labels for canonical state, preserve priority/type/parent/dependency behavior, enforce authorized status-label actors, audit/revert unauthorized transitions, and support comments, attachments metadata, archive/reopen, and issue detail. Make identifiers globally unambiguous for nested GitLab namespaces.

Do not implement native external intake in this task.

Tests:
- Contract suite for every TrackerProtocol method.
- Label/status lifecycle, parent/dependency links, comment and metadata round trips, authorization rejection, pagination, and GitLab API failures.
- Existing GitHub tracker behavior remains unchanged.

Acceptance criteria:
- A GitLab Issues project can operate the entire Oompah task and epic lifecycle without GitHub code paths.
- Status safety and audit behavior match GitHub-backed tracking.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 23:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:03
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 23:04
---
Agent completed successfully in 44s (191719 tokens)
---
author: oompah
created: 2026-07-21 23:04
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 190.1K in / 1.6K out [191.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 44s
- Log: OOMPAH-323__20260721T230345Z.jsonl
---
author: oompah
created: 2026-07-21 23:04
---
Agent completed without closing this issue (44s (191719 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 23:04
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 23:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 23:06
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-323 is a unique task.

**Search evidence:**
- Searched .oompah/tasks/ (backlog, archived, merged, done, needs-ci-fix, needs-rebase) for 'gitlab', 'GitLab', 'forge-parity', 'TrackerProtocol' — no matching tasks found.
- The only GitLab-related file is plans/gitlab-forge-parity.md, which is the design plan referenced in this task description. No other task implements GitLabIssueTracker.
- OOMPAH-282 (backlog) is about a state_branch_migration UnicodeEncodeError — unrelated.
- OOMPAH-319 is already implemented (commit 84985658b 'Add explicit forge configuration and backward-compatible project migration') and is the blocking dependency for this task. It provides the forge_kind field and project model changes that OOMPAH-323 builds on.

**Relevant files for implementation:**
- oompah/tracker.py — TrackerProtocol definition and shared utilities
- oompah/github_tracker.py — Reference implementation to model GitLabIssueTracker after
- oompah/oompah_md_tracker.py — Alternative tracker reference
- plans/gitlab-forge-parity.md — Full design specification (GitLab implementation section)
- tests/test_github_tracker.py — Contract test suite to replicate for GitLab

**Remaining work:** Implement GitLabIssueTracker (oompah/gitlab_tracker.py) with full TrackerProtocol coverage, oompah:status:* label governance, authorized actor enforcement, audit/revert, parent/dependency links via issue links, comments, pagination, and comprehensive tests.

**Recommended next focus:** feature
---
author: oompah
created: 2026-07-21 23:06
---
Agent completed successfully in 131s (5820 tokens)
---
author: oompah
created: 2026-07-21 23:07
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 53, Tool calls: 41
- Tokens: 25 in / 5.8K out [5.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 11s
- Log: OOMPAH-323__20260721T230448Z.jsonl
---
author: oompah
created: 2026-07-21 23:07
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 23:23
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 23:23
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-21 23:24
---
Understanding: OOMPAH-323 is a cross-cutting GitLab tracker implementation. I will decompose it into a core GitLab REST/protocol adapter, status-governance and relationship lifecycle work, and integration/contract coverage, with dependencies that keep each child independently actionable.
---
author: oompah
created: 2026-07-21 23:25
---
Discovery: TrackerProtocol defines the complete adapter surface in oompah/tracker.py; oompah/github_tracker.py supplies the parity model, including trusted-status ledger and candidate suppression; plans/gitlab-forge-parity.md requires encoded nested project paths, pagination, GitLab notes/labels, and issue links. No existing children were shown on the task, so three non-duplicative children were created.
---
author: oompah
created: 2026-07-21 23:25
---
Focus handoff: epic_planner\n\nOutcome: decomposed GitLab tracker delivery into OOMPAH-337 (core REST adapter/protocol registration), OOMPAH-338 (relationship and metadata lifecycle), and OOMPAH-339 (status-label authorization, audit, and revert). OOMPAH-338 and OOMPAH-339 depend on OOMPAH-337.\n\nRelevant evidence: TrackerProtocol is in oompah/tracker.py; GitHub parity and governance behavior are in oompah/github_tracker.py; design constraints are in plans/gitlab-forge-parity.md.\n\nRemaining work/risks: implement all children with mocked GitLab API contract tests, then run make test; maintain GitHub regression coverage and exclude native external intake.\n\nRecommended next focus: feature.
---
author: oompah
created: 2026-07-21 23:25
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 0, Tool calls: 17
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 50s
- Log: OOMPAH-323__20260721T232346Z.jsonl
---
<!-- COMMENTS:END -->
