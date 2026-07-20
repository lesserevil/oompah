---
id: OOMPAH-232
type: bug
status: Archived
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-45 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-45.md and /home/shedwards/.oompah/repos/trickle/.oompah/...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-18T01:08:04.577980Z'
updated_at: '2026-07-18T02:05:30.733648Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#437
  owner: lesserevil
  repo: oompah
  number: '437'
  url: https://github.com/lesserevil/oompah/issues/437
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Archived
  last_synced_at: '2026-07-18T02:05:25.187163+00:00'
  last_github_state: closed
oompah.intake:
  missing_fields: []
  scope: unknown
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: pass
  last_validated_at: '2026-07-18T01:10:07.096453+00:00'
oompah.agent_run_id: a0023f93-d4ae-4763-82e5-9e453af08f31
oompah.task_costs:
  total_input_tokens: 180624
  total_output_tokens: 1859
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 180624
      output_tokens: 1859
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 180606
    output_tokens: 1619
    cost_usd: 0.0
    recorded_at: '2026-07-18T01:59:16.579027+00:00'
  - profile: deep
    model: unknown
    input_tokens: 18
    output_tokens: 240
    cost_usd: 0.0
    recorded_at: '2026-07-18T02:01:01.174644+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-45 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-45.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/needs-human/TRICKLE-45.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-45.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/needs-human/TRICKLE-45.md. Repair the stale record before editing this task.

### Desired Behavior

The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-45 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-45.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/needs-human/TRICKLE-45.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-45.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/needs-human/TRICKLE-45.md. Repair the stale record before editing this task.

### Acceptance Criteria

- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: c5878159cd5184dd
- dedup_fingerprint: c5878159cd5184dd
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/437
- Requestor: @NVShawn
- Reference: lesserevil/oompah#437

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 01:10
---
<!-- oompah:intake-action {"action": "override_readiness", "actor": "lesserevil"} -->

Intake action: readiness override

@lesserevil recorded an owner readiness override for this issue.

Owner override accepted for Proposed to Backlog.
---
author: oompah
created: 2026-07-18 01:46
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 01:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 01:59
---
Agent completed successfully in 759s (182225 tokens)
---
author: oompah
created: 2026-07-18 01:59
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 3
- Tokens: 180.6K in / 1.6K out [182.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 12m 39s
- Log: OOMPAH-232__20260718T014642Z.jsonl
---
author: oompah
created: 2026-07-18 01:59
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-232`. Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-18 01:59
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-18 01:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 02:00
---
Understanding: This issue reports a duplicate-detection error in backend:oompah_md_tracker when the same task ID (trickle-45) exists in two different state directories (merged/ and needs-human/). The error_watcher auto-filed this as a bug. My role is Duplicate Investigator — I'll search existing tasks to check if this same root cause was already reported and fixed before proceeding to implementation.
---
author: oompah
created: 2026-07-18 02:00
---
Discovery: OOMPAH-232 is a confirmed duplicate of OOMPAH-220.

OOMPAH-220 is the canonical task for this exact bug: `oompah/oompah_md_tracker.py:871` used `logger.error()` in the duplicate-ID resolution block (`_read_records()`). The code already handled duplicates gracefully (picks most-recently-updated file, continues), but ERROR level caused `error_watcher` to auto-file a bug for every occurrence.

The fix was already applied in OOMPAH-220: `logger.error()` → `logger.warning()` (commit 625014c3). OOMPAH-220 explicitly identified OOMPAH-232 (trickle-45) as one of 12 sibling duplicates filed in the same error_watcher burst.

Archiving OOMPAH-232 as duplicate-of:OOMPAH-220.
---
author: oompah
created: 2026-07-18 02:00
---
duplicate-of:OOMPAH-220
---
author: oompah
created: 2026-07-18 02:01
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 6
- Tokens: 18 in / 240 out [258 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 17s
- Log: OOMPAH-232__20260718T015954Z.jsonl
---
<!-- COMMENTS:END -->
