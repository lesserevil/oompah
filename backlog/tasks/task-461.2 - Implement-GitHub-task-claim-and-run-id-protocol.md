---
id: TASK-461.2
title: Implement GitHub task claim and run-id protocol
status: Done
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-10 01:04'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-461.1
  - TASK-458.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - tests/test_dispatch_close_race.py
parent_task_id: TASK-461
priority: high
ordinal: 138000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
For GitHub-backed tasks, claim by writing In Progress plus Agent Run ID, then re-read and proceed only if the run ID still matches. Keep current single-process behavior for Backlog while preventing duplicate claims if multiple oompah instances exist.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Claim races are detected and skipped without starting duplicate agents.
- [ ] #2 Running state includes tracker kind and fully qualified identifier.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 00:41
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 00:41
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 00:57
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 71
- Tokens: 113 in / 3.5K out [3.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 16m 39s
- Log: TASK-461.2__20260610T004136Z.jsonl
---

author: oompah
created: 2026-06-10 00:59
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 01:03
---
Understanding: TASK-461.2 is NOT a duplicate. No existing task covers the GitHub claim-and-verify run-ID protocol. Both blockers (TASK-461.1, TASK-458.5) are Done. A previous agent run left uncommitted changes in oompah/orchestrator.py and tests/test_dispatch_close_race.py implementing the feature. My role is to verify correctness, run tests, and land the implementation.
---

author: oompah
created: 2026-06-10 01:03
---
Discovery: Implementation already present from prior agent run. Key changes: (1) oompah/orchestrator.py - Added uuid import; GitHub claim-and-verify block in _dispatch() that writes oompah.agent_run_id via set_metadata_field, re-reads via get_metadata, aborts if run_id was overwritten (another instance won the race); failure falls through gracefully with a warning; added tracker_kind to running snapshot dict (AC#2). (2) tests/test_dispatch_close_race.py - 5 new tests: race detected→abort, race won→proceeds, BacklogMd skips protocol, network failure falls through, and running snapshot exposes tracker_kind.
---

author: oompah
created: 2026-06-10 01:03
---
Verification: All tests pass. test_dispatch_close_race.py: 13/13 passed (5 new for TASK-461.2 + 8 pre-existing). test_orchestrator_merged.py: 129/129. test_github_tracker.py: 321/321. test_backlog_tracker.py + test_tracker_protocol.py + test_mixed_tracker_regression.py: included in 601 total. No regressions.
---

author: oompah
created: 2026-06-10 01:04
---
Completion: Confirmed NOT a duplicate. Implemented and landed GitHub task claim-and-verify run-ID protocol. (1) _dispatch() in oompah/orchestrator.py: for github_issues tasks, writes a uuid4 run ID to oompah.agent_run_id metadata, re-reads it, and aborts without starting a worker if another instance owns the claim. Failures fall through gracefully. BacklogMd issues skip the protocol. (2) Running snapshot includes tracker_kind (AC #2). (3) 5 new tests in test_dispatch_close_race.py cover both ACs. 601 tests pass total. Branch epic-TASK-461 pushed to origin.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented GitHub task claim-and-verify run-ID protocol in _dispatch(). For github_issues tasks: writes a uuid4 run ID to oompah.agent_run_id metadata, re-reads it, aborts if another instance owns the claim (AC#1). Failures fall through gracefully. BacklogMd issues skip the protocol. Running snapshot now includes tracker_kind (AC#2). 5 new tests in test_dispatch_close_race.py; 601 tests pass total.
<!-- SECTION:FINAL_SUMMARY:END -->
