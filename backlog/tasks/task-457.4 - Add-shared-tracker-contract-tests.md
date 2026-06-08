---
id: TASK-457.4
title: Add shared tracker contract tests
status: In Progress
assignee: []
created_date: '2026-06-08 17:56'
updated_date: '2026-06-08 23:05'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - tests
parent_task_id: TASK-457
priority: high
ordinal: 112000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Create backend-neutral contract tests for issue creation, state transitions, comments, labels, parent/child relationships, dependencies, metadata, archive detection, missing issue behavior, and candidate sorting.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Contract tests can run against BacklogMdTracker and a fake tracker implementation.
- [ ] #2 Future GitHubIssueTracker tests can reuse the same contract suite.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 20:44
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 20:44
---
Focus: Test Engineer
---

author: oompah
created: 2026-06-08 21:10
---
Agent completed successfully in 1582s (867523 tokens)
---

author: oompah
created: 2026-06-08 21:10
---
Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/Nemotron-3-Nano-30B-A3B]
- Turns: 43, Tool calls: 42
- Tokens: 821.8K in / 45.7K out [867.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 26m 22s
- Log: TASK-457.4__20260608T204438Z.jsonl
---

author: oompah
created: 2026-06-08 21:11
---
Agent completed without closing this issue (1582s (867523 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---

author: oompah
created: 2026-06-08 21:12
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 21:12
---
Focus: Test Engineer
---

author: oompah
created: 2026-06-08 22:22
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 22:22
---
Focus: Integration Tests Session Specialist
---

author: oompah
created: 2026-06-08 22:23
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-08 22:24
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 21s
- Log: TASK-457.4__20260608T222245Z.jsonl
---

author: oompah
created: 2026-06-08 22:26
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 22:26
---
Focus: Test Engineer
---

author: oompah
created: 2026-06-08 22:42
---
Run #2 [attempt=2, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 0, Tool calls: 11
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 15m 49s
- Log: TASK-457.4__20260608T222648Z.jsonl
---

author: oompah
created: 2026-06-08 22:45
---
Retrying (attempt #2, agent: standard)
---

author: oompah
created: 2026-06-08 22:45
---
Focus: Integration Tests Session Specialist
---

author: oompah
created: 2026-06-08 22:46
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 40s (attempt #3)
---

author: oompah
created: 2026-06-08 22:46
---
Run #3 [attempt=3, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 14s
- Log: TASK-457.4__20260608T224614Z.jsonl
---

author: oompah
created: 2026-06-08 22:49
---
Retrying (attempt #3, agent: standard)
---

author: oompah
created: 2026-06-08 23:05
---
Understanding: Contract test file exists at tests/test_shared_tracker_contract.py with 184 tests (107 pass, 77 fail). Two categories of failures: (1) 65 FakeTracker failures - create_issue passes invalid Issue kwargs (children, blockers, metadata) not in dataclass; fetch_children always returns []; mark_needs_human doesn't change state/add comments; set_attachments has recursive duplicate definition. (2) 12 BacklogMdTracker failures - archive_issue uses CLI which moves to archive/tasks/ not completed/, so fetch_issue_detail returns None after archiving; mark_needs_human fails because Needs Human status not in test config; several tests call pytest.fail on exception but should allow TrackerError. Plan: Fix FakeTracker in test file, add archive/tasks/ to _task_files in tracker.py, fix normalize_task to set Archived state for archive dir files, and fix test config/assertions.
---
<!-- COMMENTS:END -->
