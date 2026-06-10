---
id: TASK-449
title: '[backend:orchestrator] Failed to record candidate usage for role=deep candidate=prov-651d553c/'
status: Done
assignee: []
created_date: 2026-06-06 22:54
updated_date: 2026-06-10 00:58
labels:
- bug
dependencies: []
priority: medium
ordinal: 85000
oompah.task_costs:
  total_input_tokens: 22
  total_output_tokens: 9632
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 22
      output_tokens: 9632
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 22
    output_tokens: 9632
    cost_usd: 0.0
    recorded_at: '2026-06-10T00:24:28.848659+00:00'
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

author: oompah
created: 2026-06-10 00:24
---
VERIFICATION: All 61 tests in tests/test_candidate_selector.py pass, including 5 new TestRecordUsedDiskFull regression tests. Branch pushed to origin/TASK-449.
---
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-10 00:05

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-10 00:05

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-10 00:18

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-10 00:18

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-10 00:24

Agent completed successfully in 376s (9654 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-10 00:24

Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 40, Tool calls: 23
- Tokens: 22 in / 9.6K out [9.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 16s
- Log: TASK-449__20260610T001840Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-10 00:24

Agent completed without closing this issue (376s (9654 tokens)). Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed CandidateSelector._save() in oompah/roles.py to catch OSError (ENOSPC/disk-full) and log a warning instead of propagating. Usage tracking is best-effort and must never crash a worker. Added 5 regression tests in TestRecordUsedDiskFull. Not a duplicate — no prior task covered this path.
<!-- SECTION:FINAL_SUMMARY:END -->
