---
id: OOMPAH-156
type: bug
status: Open
priority: null
title: Deduplicate auto-filed internal error tasks before creating new tasks
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-24T16:39:49.133027Z'
updated_at: '2026-06-24T16:43:43.954284Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3c82c95c-334c-44e8-b8d1-d368a10398b6
oompah.task_costs:
  total_input_tokens: 67
  total_output_tokens: 2504
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 67
      output_tokens: 2504
      cost_usd: 0.0
  runs:
  - profile: deep
    model: unknown
    input_tokens: 67
    output_tokens: 2504
    cost_usd: 0.0
    recorded_at: '2026-06-24T16:42:56.722149+00:00'
---
## Summary

Internal backend errors from error_watcher should only create one task per stable fingerprint while an existing non-terminal task already tracks the problem. If the same internal bug repeats, oompah should attach a comment to the existing task when possible instead of creating another task. This must survive process restarts and GitHub intake resyncs, not only the current in-memory dedup window.\n\nAcceptance criteria:\n- Before auto-filing an internal error task, error_watcher searches existing tasks for the same dedup fingerprint.\n- If a non-terminal matching task exists, no new task is created.\n- Repeated occurrences add a concise comment to the existing task when supported.\n- Different fingerprints still create separate tasks.\n- Tests cover duplicate suppression across a fresh ErrorWatcher instance.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-24 16:40
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-06-24 16:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-24 16:41
---
Understanding: Confirmed NOT a duplicate. No prior task covers implementing dedup in error_watcher. The bug is clearly real: OOMPAH-50 and OOMPAH-51 (archived) were both filed with fingerprint fab624f77cb2c7ae, and proposed tasks OOMPAH-62, OOMPAH-82, OOMPAH-113, OOMPAH-118, OOMPAH-125, OOMPAH-146, OOMPAH-154 all share the same fingerprint from repeated auto-filing. Plan: (1) read error_watcher.py and existing tests, (2) implement dedup check against task store before creating tasks, (3) add comment to existing task on repeated occurrence, (4) write tests covering cross-instance dedup.
---
author: oompah
created: 2026-06-24 16:42
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 49
- Tokens: 67 in / 2.5K out [2.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 21s
- Log: OOMPAH-156__20260624T164047Z.jsonl
---
author: oompah
created: 2026-06-24 16:43
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-06-24 16:43
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
