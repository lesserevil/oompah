---
id: TASK-449
title: >-
  [backend:orchestrator] Failed to record candidate usage for role=deep
  candidate=prov-651d553c/
status: Backlog
assignee: []
created_date: '2026-06-06 22:54'
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
