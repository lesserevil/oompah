---
id: TASK-455.2
title: Resolve source commits for release picks
status: Done
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 22:54'
labels:
  - task
dependencies:
  - TASK-454.4
parent_task_id: TASK-455
priority: high
ordinal: 97000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Determine the commit set to cherry-pick from a source task. Prefer explicit commits in metadata, otherwise resolve from the merged source PR/branch. Record the resolved commits back into metadata for repeatability.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-08 20:14

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-08 20:14

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-08 20:40

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-08 20:40

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-08 20:44

Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/Nemotron-3-Nano-30B-A3B]
- Turns: 12, Tool calls: 12
- Tokens: 181.5K in / 4.0K out [185.5K total]
- Cost: $0.0000
- Exit: stalled, Duration: 3m 45s
- Log: TASK-455.2__20260608T204036Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-08 20:44

Agent stalled 1 time(s) (225s (185489 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-08 20:45

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-08 20:46

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9
author: oompah
created: 2026-06-08 21:18

Agent completed successfully in 1970s (1417130 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 10
author: oompah
created: 2026-06-08 21:18

Run #2 [attempt=2, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-super-v3]
- Turns: 52, Tool calls: 51
- Tokens: 1.4M in / 43.9K out [1.4M total]
- Cost: $0.0000
- Exit: normal, Duration: 32m 50s
- Log: TASK-455.2__20260608T204616Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 11
author: oompah
created: 2026-06-08 21:18

Agent completed without closing this issue (1970s (1417130 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 12
author: oompah
created: 2026-06-08 21:19

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 13
author: oompah
created: 2026-06-08 21:19

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 14
author: oompah
created: 2026-06-08 22:22

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 15
author: oompah
created: 2026-06-08 22:22

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 16
author: oompah
created: 2026-06-08 22:22

Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 17
author: oompah
created: 2026-06-08 22:22

Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 30s
- Log: TASK-455.2__20260608T222225Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 18
author: oompah
created: 2026-06-08 22:25

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented release-pick commit resolver (oompah/release_pick_commit_resolver.py) with three resolution strategies: (1) explicit commits from metadata, (2) SCM PR lookup for merged PRs, (3) git rev-list fallback. The resolve_and_record_commits function persists resolved commits back to Backlog metadata for idempotent repeatability. All 57 tests pass, including edge cases for empty commits, SCM errors, and metadata write-back idempotency.
<!-- SECTION:FINAL_SUMMARY:END -->
