---
id: OOMPAH-231
type: bug
status: Archived
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-44 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-44.md and
  /home/shedwards/.oompah/repos/trickle/.oo...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-18T01:07:55.118753Z'
updated_at: '2026-07-18T02:05:26.326264Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#436
  owner: lesserevil
  repo: oompah
  number: '436'
  url: https://github.com/lesserevil/oompah/issues/436
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Archived
  last_synced_at: '2026-07-18T02:05:21.090759+00:00'
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
  last_validated_at: '2026-07-18T01:09:52.990425+00:00'
oompah.agent_run_id: 71664ff6-0a38-4176-a2ee-3d8d62ed7272
oompah.task_costs:
  total_input_tokens: 168005
  total_output_tokens: 2377
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 168005
      output_tokens: 2377
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 167969
    output_tokens: 1597
    cost_usd: 0.0
    recorded_at: '2026-07-18T01:59:26.184327+00:00'
  - profile: deep
    model: unknown
    input_tokens: 36
    output_tokens: 780
    cost_usd: 0.0
    recorded_at: '2026-07-18T02:02:51.420875+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-44 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-44.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-44.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-44.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-44.md. Repair the stale record before editing this task.

### Desired Behavior

The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-44 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-44.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-44.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-44.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-44.md. Repair the stale record before editing this task.

### Acceptance Criteria

- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 8d7cd7bfad9137f9
- dedup_fingerprint: 8d7cd7bfad9137f9
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/436
- Requestor: @NVShawn
- Reference: lesserevil/oompah#436

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 01:47
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 01:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 01:59
---
Agent completed successfully in 737s (169566 tokens)
---
author: oompah
created: 2026-07-18 01:59
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 3
- Tokens: 168.0K in / 1.6K out [169.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 12m 17s
- Log: OOMPAH-231__20260718T014716Z.jsonl
---
author: oompah
created: 2026-07-18 01:59
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-231`. Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-18 02:00
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-18 02:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 02:02
---
Understanding: OOMPAH-231 reports a 'Duplicate native oompah task ID trickle-44' error auto-filed by error_watcher after backend:oompah_md_tracker detected the same task in two state directories (in-progress/ and merged/). My role is Duplicate Investigator. I will search for identical or substantially equivalent prior reports before any implementation.
---
author: oompah
created: 2026-07-18 02:02
---
Discovery: OOMPAH-231 is a CONFIRMED DUPLICATE of OOMPAH-220.

**Evidence:**
- OOMPAH-220 (In Progress) is titled '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-30...' — identical error class, same root cause.
- Root cause (confirmed in OOMPAH-220 comments): oompah/oompah_md_tracker.py line 871 uses logger.error() inside _read_records() when a task file is found in two status directories. The code already handles this gracefully (picks most-recently-updated record), but ERROR level logging triggers error_watcher to auto-file a bug task.
- OOMPAH-220's Maintenance Engineer comment documents both the fix (logger.error → logger.warning at line 871) and passing tests (make test 9054 passed). Branch OOMPAH-220 exists on origin.
- Siblings already archived as duplicate-of:OOMPAH-220: OOMPAH-221 (trickle-31), OOMPAH-222 (trickle-32), OOMPAH-223 (trickle-36), OOMPAH-224 (trickle-37).
- OOMPAH-231 (trickle-44) is one of the 13 sibling tasks identified in OOMPAH-220's handoff comment (OOMPAH-220 through OOMPAH-232).

**Conclusion:** Archiving OOMPAH-231 as duplicate-of:OOMPAH-220. No implementation needed here — the fix is tracked in OOMPAH-220.
---
author: oompah
created: 2026-07-18 02:02
---
duplicate-of:OOMPAH-220
---
author: oompah
created: 2026-07-18 02:02
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 18
- Tokens: 36 in / 780 out [816 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 51s
- Log: OOMPAH-231__20260718T020010Z.jsonl
---
<!-- COMMENTS:END -->
