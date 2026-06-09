---
id: TASK-458.2
title: Parse and format GitHub issue identifiers
status: In Progress
assignee: []
created_date: '2026-06-08 17:56'
updated_date: '2026-06-09 06:13'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-458.1
  - TASK-457.2
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/github_tracker.py
  - tests
parent_task_id: TASK-458
priority: high
ordinal: 116000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement parser/formatter support for fully qualified identifiers such as owner/repo#1234, central task hub short display identifiers, URL-safe route forms, and branch-safe slugs. Bare numeric identifiers must not be accepted as canonical.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Identifier parsing rejects ambiguous bare numbers.
- [ ] #2 Display identifiers and branch slugs are stable and filesystem-safe.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 05:40
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 05:40
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 05:41
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 05:41
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 27s
- Log: TASK-458.2__20260609T054023Z.jsonl
---

author: oompah
created: 2026-06-09 05:44
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 05:44
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 05:44
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-09 05:45
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 39s
- Log: TASK-458.2__20260609T054431Z.jsonl
---

author: oompah
created: 2026-06-09 05:47
---
Retrying (attempt #2, agent: standard)
---

author: oompah
created: 2026-06-09 05:48
---
Focus: Maintenance Engineer
---

author: oompah
created: 2026-06-09 05:52
---
Run #3 [attempt=3, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 11, Tool calls: 11
- Tokens: 277.8K in / 913 out [278.7K total]
- Cost: $0.0000
- Exit: stalled, Duration: 4m 52s
- Log: TASK-458.2__20260609T054812Z.jsonl
---

author: oompah
created: 2026-06-09 05:53
---
Agent stalled 1 time(s) (292s (278706 tokens)). Escalating from 'standard' to 'deep'. Retrying in 40s (attempt #3)
---

author: oompah
created: 2026-06-09 05:54
---
Retrying (attempt #3, agent: deep)
---

author: oompah
created: 2026-06-09 05:54
---
Focus: Maintenance Engineer
---

author: oompah
created: 2026-06-09 05:59
---
Agent stalled — no productive actions (writes/commands) for 10 consecutive turns (287s (430546 tokens)). Retrying in 80s (attempt #4)
---

author: oompah
created: 2026-06-09 05:59
---
Run #4 [attempt=4, profile=deep, role=deep -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 11, Tool calls: 11
- Tokens: 429.7K in / 811 out [430.5K total]
- Cost: $0.0000
- Exit: stalled, Duration: 4m 47s
- Log: TASK-458.2__20260609T055506Z.jsonl
---

author: oompah
created: 2026-06-09 06:02
---
Retrying (attempt #4, agent: standard)
---

author: oompah
created: 2026-06-09 06:02
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 06:03
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 160s (attempt #5)
---

author: oompah
created: 2026-06-09 06:03
---
Run #5 [attempt=5, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 56s
- Log: TASK-458.2__20260609T060246Z.jsonl
---

author: oompah
created: 2026-06-09 06:06
---
Retrying (attempt #5, agent: standard)
---

author: oompah
created: 2026-06-09 06:08
---
Understanding: Implementing GitHub issue identifier parser/formatter in oompah/github_tracker.py. Need to add: (1) parse_github_identifier() - accepts owner/repo#1234, rejects bare numbers; (2) format functions for display (tasks#1234), URL-safe routes, and branch slugs (gh-1234); (3) GitHubIdentifier dataclass; (4) tests covering all acceptance criteria. Dependency TASK-458.1 (auth/client layer) is Done. TASK-457.2 (Issue model fields) is Done - Issue model already has tracker_kind, owner, repo, issue_number, display_identifier fields.
---

author: oompah
created: 2026-06-09 06:13
---
Implementation complete. Added to oompah/github_tracker.py: (1) GitHubIdentifier frozen dataclass with canonical/display/url_safe/branch_slug properties; (2) GitHubIdentifierError exception; (3) parse_github_identifier() which accepts owner/repo#1234 and explicitly rejects bare numbers with actionable error; (4) github_identifier_to_issue_fields() helper to map to Issue model fields; (5) GitHubIssueTracker.parse_identifier() (wraps as TrackerError) and identifier_for_number() helpers. Bare number rejection satisfies AC#1; stable branch slugs (gh-1234) and display form (repo#1234) satisfy AC#2.
---

author: oompah
created: 2026-06-09 06:13
---
Tests: 123/123 passing in test_github_tracker.py. Added 54 new test cases (TestGitHubIdentifier, TestParseGitHubIdentifier, TestGitHubIdentifierToIssueFields, TestGitHubIssueTrackerIdentifierHelpers). One pre-existing flaky test in test_collapsed_epics.py (ordering-sensitive, passes in isolation, was failing before my changes too).
---
<!-- COMMENTS:END -->
