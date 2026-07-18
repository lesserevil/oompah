---
id: OOMPAH-227
type: bug
status: Archived
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-40 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-40.md and /home/shedwards/.oompah/repos/trickle/.oompah/ta...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-18T01:07:37.379315Z'
updated_at: '2026-07-18T02:03:59.588588Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#432
  owner: lesserevil
  repo: oompah
  number: '432'
  url: https://github.com/lesserevil/oompah/issues/432
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Open
  last_synced_at: '2026-07-18T01:47:12.021389+00:00'
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
  last_validated_at: '2026-07-18T01:09:06.803474+00:00'
oompah.agent_run_id: e6a2df71-bc42-413d-ba83-8d49cadf867f
oompah.task_costs:
  total_input_tokens: 24
  total_output_tokens: 418
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 24
      output_tokens: 418
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 24
    output_tokens: 418
    cost_usd: 0.0
    recorded_at: '2026-07-18T02:03:56.703103+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-40 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-40.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-40.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-40.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-40.md. Repair the stale record before editing this task.

### Desired Behavior

The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-40 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-40.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-40.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-40.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-40.md. Repair the stale record before editing this task.

### Acceptance Criteria

- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 256baabca9a2bfd3
- dedup_fingerprint: 256baabca9a2bfd3
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/432
- Requestor: @NVShawn
- Reference: lesserevil/oompah#432

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 02:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 02:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 02:02
---
Understanding: This bug reports that backend:oompah_md_tracker emits an error when the same task ID (trickle-40) exists in two different state directories (done/ and merged/). The error_watcher captured it and auto-filed this task. My role as Duplicate Investigator is to determine whether this has already been reported and handled before implementing any fix.
---
author: oompah
created: 2026-07-18 02:03
---
Discovery: OOMPAH-227 is a confirmed duplicate of OOMPAH-220.

**Evidence:**
- OOMPAH-220 is the canonical task for this exact bug: backend:oompah_md_tracker uses logger.error() in the duplicate-ID resolution block (_read_records() ~line 871), causing error_watcher to auto-file bugs for each occurrence.
- OOMPAH-220's own comments (from the duplicate_detector agent) explicitly list 'OOMPAH-227 (trickle-40)' as one of 12 sibling duplicates filed in the same error_watcher burst.
- OOMPAH-220 was already fixed: logger.error() → logger.warning() at oompah/oompah_md_tracker.py:871 (commit 625014c3, PR #438, merged).
- The fix includes a regression test: test_duplicate_task_id_logs_warning_not_error in tests/test_oompah_md_tracker.py.

**Conclusion:** No implementation needed. The root cause is resolved in OOMPAH-220. Archiving OOMPAH-227 as duplicate-of:OOMPAH-220.
---
author: oompah
created: 2026-07-18 02:03
---
duplicate-of:OOMPAH-220
---
author: oompah
created: 2026-07-18 02:03
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 11
- Tokens: 24 in / 418 out [442 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 31s
- Log: OOMPAH-227__20260718T020231Z.jsonl
---
<!-- COMMENTS:END -->
