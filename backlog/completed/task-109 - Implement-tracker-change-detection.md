---
id: TASK-109
title: Implement tracker change-detection
status: Done
assignee: []
created_date: 2026-03-08 21:18
updated_date: 2026-03-08 21:24
labels:
- archive:yes
- draft
- merged
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-k3d.1
  state: closed
  parent_id: oompah-k3d
  dependencies: []
  branch_name: oompah-k3d.1
  target_branch: null
  url: null
  created_at: '2026-03-08T21:18:40Z'
  updated_at: '2026-03-08T21:24:20Z'
  closed_at: '2026-03-08T21:24:20Z'
parent: TASK-108
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a lightweight change-detection query that checks if the working set has changed since the last poll
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: ad5d06a3-640f-4cae-886c-e6d8b38b5036
author: oompah
created: 2026-03-08T21:19:03Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a5663fa3-45dc-4b2a-9eba-47d8ac3b4dd7
author: oompah
created: 2026-03-08T21:19:04Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a77ecd94-1c4f-45b2-ad7f-39e55fcfab3a
author: oompah
created: 2026-03-08T21:19:27Z

Agent stalled 1 time(s) (24s (123096 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f3ac2af6-61e8-4f8e-8a27-f3c00c3082cf
author: oompah
created: 2026-03-08T21:19:38Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ff5e8e12-95ab-4155-b72f-7fdd7a4d19f6
author: oompah
created: 2026-03-08T21:19:38Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 90355983-16ad-4c42-97b3-f45307c591f5
author: oompah
created: 2026-03-08T21:20:17Z

I understand the issue: The orchestrator polls the beads tracker every 30s by running expensive 'bd list' subprocess calls to fetch all candidate issues. The goal is to add a lightweight change-detection method to BeadsTracker that can cheaply determine if the tracker's working set has changed since the last poll, so the orchestrator can skip expensive fetches when nothing has changed.

My plan:
1. Add a 'has_changes_since()' method to BeadsTracker that runs 'bd status --json' (or similar) to get a fingerprint/hash of the current tracker state
2. Store the last-known fingerprint and compare on subsequent calls
3. Add a 'working_set_fingerprint()' method that returns a comparable value (e.g., hash of issue IDs + updated_at timestamps)
4. Write comprehensive tests for the new methods
5. This is step 1 of the parent epic - just the tracker change detection, not the orchestrator integration
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 122110d6-889c-4631-910b-e6aeb6e86412
author: oompah
created: 2026-03-08T21:21:05Z

Discovery: The bd CLI provides two useful change-detection mechanisms:
1. 'bd vc status --json' returns the current Dolt branch + commit hash. If the commit changes, the working set has been modified.
2. 'bd status --json --no-activity' returns counts by status (cheap). A change in counts means the working set changed.
3. 'bd count --by-status --json' returns grouped counts.

My approach: Add a 'working_set_fingerprint()' method that runs 'bd vc status --json' (cheapest - returns just branch+commit) as the primary strategy, with 'bd status --json --no-activity' as fallback. Then add a 'has_changed()' method that compares the current fingerprint with the last-known one. The Dolt commit hash is the ideal signal - if it hasn't changed, the database hasn't changed. This replaces expensive 'bd list' calls with a single cheap command.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 01ac0291-cc34-4b6d-b43f-c236665dadec
author: oompah
created: 2026-03-08T21:23:28Z

Implementation complete. Added 3 new methods to BeadsTracker in oompah/tracker.py:

1. **working_set_fingerprint()** — Returns a lightweight fingerprint of the current tracker state. Uses two strategies: (a) Dolt commit hash via 'bd vc status --json' (exact, cheapest — single subprocess returning ~50 bytes), with (b) status summary hash via 'bd status --json --no-activity' as fallback for non-Dolt backends.

2. **has_changed()** — Compares the current fingerprint to the last-known one. Returns True on first call, on change, or on error (fail-open). Returns False only when fingerprint matches. Designed for use in the orchestrator's poll loop before fetch_candidate_issues().

3. **reset_fingerprint()** — Clears the stored fingerprint, forcing the next has_changed() to return True. For use after manual refresh requests or on startup.

Also added a last_fingerprint property for observability.

Key design decisions:
- Fail-open: if fingerprint can't be computed, assume changed (never skip a fetch due to error)
- Stored fingerprint only updated by has_changed(), not working_set_fingerprint() (clean separation)
- No new dependencies — uses only stdlib (hashlib, json)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f6bb2fce-2d00-4328-bc36-bde34ae7e8c9
author: oompah
created: 2026-03-08T21:23:35Z

Verification: All 27 new tests pass. All 25 existing tracker tests pass. The 12 pre-existing failures in the test suite are unrelated (missing yaml/fastapi deps in this worktree environment). Test coverage includes: both fingerprint strategies, fallback behavior, deterministic hashing, change detection lifecycle, fail-open on errors, transient error recovery, strategy switching, fingerprint reset, and the last_fingerprint property.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6f5b4f42-7d2d-43af-93c5-a06efcaf2e33
author: oompah
created: 2026-03-08T21:24:14Z

PR created: https://github.com/lesserevil/oompah/pull/40

Summary of deliverables:
- 3 new methods on BeadsTracker: working_set_fingerprint(), has_changed(), reset_fingerprint()
- 1 new property: last_fingerprint
- 27 new tests in tests/test_tracker_change_detection.py
- No new dependencies, no changes to existing behavior
- This is step 1 of the parent epic (oompah-k3d) — the tracker-level primitive for change detection
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
