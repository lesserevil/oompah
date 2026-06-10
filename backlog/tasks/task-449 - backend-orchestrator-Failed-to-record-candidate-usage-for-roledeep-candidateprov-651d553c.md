---
id: TASK-449
title: >-
  [backend:orchestrator] Failed to record candidate usage for role=deep
  candidate=prov-651d553c/
status: In Progress
assignee: []
created_date: '2026-06-06 22:54'
updated_date: '2026-06-10 00:23'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 85000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Failed to record candidate usage for role=deep candidate=prov-651d553c/

OSError: [Errno 28] No space left on device

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/shedwards/src/oompah/oompah/orchestrator.py", line 8491, in _run_worker
    self._candidate_selector.record_used(
  File "/home/shedwards/src/oompah/oompah/roles.py", line 744, in record_used
    self._save()
  File "/home/shedwards/src/oompah/oompah/roles.py", line 664, in _save
    with open(self.path, "w") as f:
         ^^^^^^^^^^^^^^^^^^^^
OSError: [Errno 28] No space left on device
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 00:05
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 00:05
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-10 00:20
---
UNDERSTANDING: This is NOT a duplicate - no similar tasks found. The issue is that OSError (ENOSPC) from a disk-full condition propagates from roles.py _save() through record_used() and crashes the worker. Since record_used is called inside an exception handler in orchestrator.py (handling a prior error), the OSError from disk-full corrupts the exception chain and causes the worker to fail hard. Fix: wrap _save() or record_used() to catch OSError and log a warning, so disk-full is non-fatal for usage tracking.
---

author: oompah
created: 2026-06-10 00:21
---
DISCOVERY: Root cause confirmed in oompah/roles.py CandidateSelector._save() (line ~664). The method has no OSError handling — when disk is full, the exception propagates through record_used() to the caller. Orchestrator.py already has a try/except around the call site (added at some point), but _save() itself should be defensive since usage tracking is non-critical. Fix: catch OSError in CandidateSelector._save() and log a warning instead of propagating. Also need a regression test.
---

author: oompah
created: 2026-06-10 00:23
---
IMPLEMENTATION: Fixed CandidateSelector._save() in oompah/roles.py to catch OSError (e.g. ENOSPC) and log a warning instead of propagating. Usage tracking is best-effort - a disk-full condition should never crash a worker. Also added 5 regression tests in tests/test_candidate_selector.py (TestRecordUsedDiskFull) covering: no raise on OSError, warning log emitted, in-memory state still updated, returns None, and subsequent calls succeed after disk recovers.
---
<!-- COMMENTS:END -->
