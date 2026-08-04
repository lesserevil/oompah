---
id: OOMPAH-533
type: task
status: Archived
priority: 3
title: Expose duplicate-screening state in the API and dashboard
parent: OOMPAH-528
children: []
blocked_by:
- OOMPAH-532
labels: []
assignee: null
created_at: '2026-07-28T21:19:45.110386Z'
updated_at: '2026-08-04T23:12:57.640492Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-f7935578de9c: '2026-08-04T23:12:54.256797+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-533
    target_state: Archived
    evidence_fingerprint: e610bae7c893dac11cb38bb0e58d003450bc9faa874eb33a3b994afb4f62b354
    audit_ids:
    - audit-a7689a4beebe
    kind: result
    applied: true
    retired_at: '2026-08-04T23:12:54.256809+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-533
    audit_id: audit-a7689a4beebe
    attempt_id: attempt-f7935578de9c
    target_state: Archived
    evidence_fingerprint: e610bae7c893dac11cb38bb0e58d003450bc9faa874eb33a3b994afb4f62b354
    status: Archived
    audit_ids:
    - audit-a7689a4beebe
    applied: false
    created_at: '2026-08-04T23:12:54.256826+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a7689a4beebe
    project_id: proj-14849f1b
    task_id: OOMPAH-533
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e610bae7c893dac11cb38bb0e58d003450bc9faa874eb33a3b994afb4f62b354
    attempts:
    - version: 1
      attempt_id: attempt-6d5bbed0f36d
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e610bae7c893dac11cb38bb0e58d003450bc9faa874eb33a3b994afb4f62b354
      created_at: '2026-08-04T22:41:40.426681+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T22:41:40.426681+00:00'
      branch_key: OOMPAH-533
      ended_at: '2026-08-04T22:54:29.867988+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-f7935578de9c
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e610bae7c893dac11cb38bb0e58d003450bc9faa874eb33a3b994afb4f62b354
      created_at: '2026-08-04T22:54:32.002844+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T22:54:32.002844+00:00'
      branch_key: OOMPAH-533
      candidate_rotation_count: 1
      verdict: pass
      completed_at: '2026-08-04T23:12:54.256637+00:00'
      ended_at: '2026-08-04T23:12:54.256637+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T22:36:56.312957+00:00'
    updated_at: '2026-08-04T23:12:54.256637+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-6d5bbed0f36d
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e610bae7c893dac11cb38bb0e58d003450bc9faa874eb33a3b994afb4f62b354
    created_at: '2026-08-04T22:41:40.426681+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T22:41:40.426681+00:00'
    branch_key: OOMPAH-533
    ended_at: '2026-08-04T22:54:29.867988+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-f7935578de9c
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e610bae7c893dac11cb38bb0e58d003450bc9faa874eb33a3b994afb4f62b354
    created_at: '2026-08-04T22:54:32.002844+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T22:54:32.002844+00:00'
    branch_key: OOMPAH-533
    candidate_rotation_count: 1
oompah.task_costs:
  total_input_tokens: 20
  total_output_tokens: 133
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 20
      output_tokens: 133
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 20
    output_tokens: 133
    cost_usd: 0.0
    recorded_at: '2026-08-04T22:43:55.949419+00:00'
---
## Summary

Make pre-dispatch duplicate screening understandable to operators after the lifecycle from OOMPAH-529 through OOMPAH-532 is functional.

Implementation scope:
- Add a stable API representation of duplicate screening to issue detail/state payloads: unchecked, running, checked, or stale; include checked_at, detector identity/version, claim start/expiry for running work, and matched identifiers for duplicate verdicts. Do not expose internal prompts, secrets, or full agent output.
- Ensure active-agent/activity endpoints identify a duplicate preflight run as screening rather than implementation while the underlying task remains Open.
- Update the dashboard task card/detail UI to display a compact Duplicate check badge/state. Running must update through the existing refresh/WebSocket mechanism; checked/stale must render after reload.
- Add accessible text/title details explaining why a result is stale and when it was checked. Do not rely on color alone.
- Add aggregate state/metrics fields needed to explain why an Open task is not yet eligible for implementation, including waiting for duplicate check and duplicate check running.
- Keep payload parsing backward compatible when older servers or tasks have no screening metadata.

Relevant context/files:
- oompah/server.py issue/state/activity endpoints.
- oompah/templates/dashboard.html and existing client-side issue rendering.
- Metadata helpers from OOMPAH-529 and orchestrator run state from OOMPAH-530/OOMPAH-532.
- Existing API/dashboard tests should be extended rather than replaced.

Required tests:
- API serialization for all four states, malformed/legacy metadata, and safe field filtering.
- Activity payload distinguishes preflight from implementation.
- Dashboard rendering tests for unchecked, running, checked, stale, and missing metadata.
- Refresh/update regression proving an Open task changes badges when screening starts/completes without changing to In Progress.
- Accessibility assertion for textual status information.

Acceptance criteria:
1. Operators can distinguish Open-and-waiting, Open-and-screening, and Open-and-checked tasks.
2. The agent list does not claim that implementation is underway during duplicate preflight.
3. API additions are backward compatible and do not expose sensitive worker data.
4. UI state updates without a full service restart and remains correct after page reload.
5. Focused API and dashboard tests pass through the appropriate Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 21:43
---
Claimed by the current interactive Codex session before OOMPAH-532 completion. API/dashboard work is underway on epic-OOMPAH-528; do not dispatch another agent.
---
author: oompah
created: 2026-07-28 21:44
---
Implemented and pushed in 209260174: safe board/detail/activity API fields, screening work_kind, accessible dashboard states, refresh fingerprint integration, and protection against optimistic In Progress movement. Server/dashboard result: 1716 passed.
---
author: oompah
created: 2026-07-28 21:44
---
Duplicate-screening API/dashboard observability implemented and pushed in 209260174.
---
author: oompah
created: 2026-07-28 22:03
---
The parent epic OOMPAH-528 merged from epic-OOMPAH-528, but this task was Open with work branch unset. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-28 22:05
---
The parent epic OOMPAH-528 merged from epic-OOMPAH-528, but this task was Needs Human with work branch unset. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-28 22:13
---
Resolved: this was a false unlanded-work alert from the stale managed epic worktree. PR #568 merged verified head c4c7f5dfa into main as 70771b4e9. The flagged 92aa5e5c2 commit was a separate incomplete scheduler attempt that explicitly left dispatch integration pending; it was intentionally rejected before review and is not required task work. The stale local worktree/branch has now been removed, while origin/epic-OOMPAH-528 and all completed implementation remain preserved in main. Final branch validation was 13,070 passed, 7 skipped. No human recovery action is required.
---
author: oompah
created: 2026-07-28 22:13
---
Verified the completed duplicate-preflight work landed in PR #568; removed stale divergent worktree evidence.
---
author: oompah
created: 2026-08-04 22:37
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 22:41
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 22:41
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 22:43
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 3
- Tokens: 20 in / 133 out [153 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 13s
- Log: OOMPAH-533__20260804T224158Z.jsonl
---
author: oompah
created: 2026-08-04 22:54
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 22:54
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
