---
id: TASK-455.2
title: Resolve source commits for release picks
status: In Progress
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 21:24'
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
author: oompah
created: 2026-06-08 20:14
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 20:14
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 20:40
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 20:40
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 20:44
---
Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/Nemotron-3-Nano-30B-A3B]
- Turns: 12, Tool calls: 12
- Tokens: 181.5K in / 4.0K out [185.5K total]
- Cost: $0.0000
- Exit: stalled, Duration: 3m 45s
- Log: TASK-455.2__20260608T204036Z.jsonl
---

author: oompah
created: 2026-06-08 20:44
---
Agent stalled 1 time(s) (225s (185489 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-08 20:45
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 20:46
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 21:18
---
Agent completed successfully in 1970s (1417130 tokens)
---

author: oompah
created: 2026-06-08 21:18
---
Run #2 [attempt=2, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-super-v3]
- Turns: 52, Tool calls: 51
- Tokens: 1.4M in / 43.9K out [1.4M total]
- Cost: $0.0000
- Exit: normal, Duration: 32m 50s
- Log: TASK-455.2__20260608T204616Z.jsonl
---

author: oompah
created: 2026-06-08 21:18
---
Agent completed without closing this issue (1970s (1417130 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---

author: oompah
created: 2026-06-08 21:19
---
Agent dispatched (profile: deep)
---

author: oompah
created: 2026-06-08 21:24
---
Understanding: Not a duplicate. TASK-455.2 implements release_pick_commit_resolver.py — a module that resolves which commits to cherry-pick for a BackportEntry. Logic: (1) if BackportEntry.commits is already populated, return those directly; (2) otherwise find the merged PR for the source task's branch via SCM (find_pr_for_branch + get_pr_commits); (3) fall back to git rev-list on the repo_path if SCM lookup fails. Resolved commits are recorded back to BackportEntry.commits and persisted via tracker.set_metadata_field. Tests will cover all 3 paths, edge cases, and metadata write-back idempotency.
---
<!-- COMMENTS:END -->
