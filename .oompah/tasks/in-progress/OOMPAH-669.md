---
id: OOMPAH-669
type: bug
status: In Progress
priority: 1
title: Same-head task resubmission must restore Ready to Integrate lifecycle
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-07-31T21:52:16.588312Z'
updated_at: '2026-07-31T23:13:21.957729Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2fdeca993d4c091dd5af6a63ea4ddf674c7e65b46f17ae5430e199130f7db418
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T23:01:50.853075+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: OOMPAH-570, OOMPAH-574, OOMPAH-628, and OOMPAH-661\
    \ are the closest records, but all are terminal and address queue rearming, gate-cache\
    \ retries, integrated-row reflow, or stale worker retries\u2014not `_persist_worker_submission`\
    \ failing to restore the canonical lifecycle. Active tasks OOMPAH-651, OOMPAH-664\u2013\
    667, and OOMPAH-670 are unrelated."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: de234723-7746-4658-8f43-8a3a9bbf3db5
oompah.task_costs:
  total_input_tokens: 834061
  total_output_tokens: 5102
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 834061
      output_tokens: 5102
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 834061
    output_tokens: 5102
    cost_usd: 0.0
    recorded_at: '2026-07-31T23:01:50.846145+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-669__20260731T225919Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: duplicate_detector
    source_branch: OOMPAH-669
    source_sha: d96740a6ecdca353e40ef87e94a4ee91b8828df0
    completed_at: '2026-07-31T23:01:50.885987+00:00'
---
## Summary

Triggered by: OOMPAH-668

Live production reproduction on OOMPAH-668 on 2026-07-31: after an exact-head delivery error, the task was moved through Needs Human/In Progress and resubmitted from its clean registered worktree at the same pushed branch/head. POST /api/v1/issues/{id}/submit returned 201 and the task CLI printed Submitted for integration, but the canonical lifecycle remained In Progress and no new submission comment was written. Root cause is _persist_worker_submission in oompah/server.py: when the existing oompah.integration object has the same task_branch/head_sha, it returns early before tracker.update_issue(... Ready to Integrate) and before recording the new summary. This strands an explicitly resubmitted task despite a success response and forces a content-identical empty commit to change the head. Implement explicit-submit idempotency so every accepted submit request atomically reconciles lifecycle to Ready to Integrate and records/rearms delivery as appropriate, while duplicate requests already in Ready/queued/integrating stay idempotent and background synchronization cannot create loops. Coordinate with the existing queue rearm behavior from OOMPAH-570 and OOMPAH-628 rather than duplicating it. Relevant files: oompah/server.py submission persistence/API, integration queue wiring, task CLI/API response contract, and focused submission/reflow tests. Required deterministic tests: same branch/head resubmitted from In Progress, Needs Human, and Needs CI Fix becomes Ready and runs exactly one fresh delivery; duplicate same-head submission already Ready does not duplicate comments/gates/leases; concurrent status-change-versus-submit has one atomic authority winner; restart preserves the rearmed state; unrelated tasks/projects stay isolated. Acceptance: a 201 submit response always corresponds to durable Ready-to-Integrate lifecycle for that accepted generation, same-head recovery never needs an empty commit, no duplicate integration loop is introduced, focused tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 22:59
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-07-31 22:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 23:01
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 19
- Tokens: 834.1K in / 5.1K out [839.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 37s
- Log: OOMPAH-669__20260731T225919Z.jsonl
---
author: oompah
created: 2026-07-31 23:02
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-31 23:02
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-31 23:09
---
Understanding: The bug is in _persist_worker_submission (oompah/server.py). When a task has an existing 'ready' integration record with matching head/branch AND its canonical tracker status was moved via other paths (In Progress / Needs Human / Needs CI Fix), _submission_record returns the same existing IntegrationRecord object. Then _persist_worker_submission's guard 'if record is existing and head/branch match' fires and returns early — WITHOUT reconciling the tracker status back to Ready to Integrate or posting the fresh submission comment. The 201 response lies about the actual lifecycle.

Plan: swap the identity-based idempotency guard for a lifecycle-based one. Fully idempotent only when (a) the durable record is truly unchanged AND (b) the canonical tracker status is already Ready to Integrate. Any other observed status must trigger tracker.update_issue(Ready to Integrate) + fresh summary comment. Metadata is rewritten only for a genuinely new record. This keeps duplicate submits at Ready/queued/integrating idempotent while making same-head recovery from other statuses correct. Queue rearm behavior from OOMPAH-628 stays as-is.

Tests to add in tests/test_worker_submission.py: same-head resubmit from In Progress / Needs Human / Needs CI Fix atomically writes status+comment; duplicate same-head submit already at Ready to Integrate is fully idempotent; queue rearm still fires; unrelated projects stay isolated.
---
author: oompah
created: 2026-07-31 23:13
---
Implementation: fixed _persist_worker_submission in oompah/server.py.

- Replaced the identity guard 'record is existing' with a lifecycle-aware guard: fully idempotent only when the durable record is unchanged AND canonical_status == READY_TO_INTEGRATE. Any other observed canonical status (In Progress, Needs Human, Needs CI Fix, ...) triggers tracker.update_issue(Ready to Integrate) + fresh summary comment so the 201 response is truthful.
- Metadata rewrite is now skipped only when reuses_existing_record=True (same head/branch + reused IntegrationRecord). This avoids identical rewrites while still reconciling lifecycle. Fresh-generation submits (new head, or first-time submit) still write metadata.
- Removed 'integrated' from _submission_record's reuse-existing set so an explicit integrated → resubmit rebuilds a fresh 'ready' record; that in turn keeps _enqueue_worker_submission's rearm_integrated=True (OOMPAH-628) firing correctly.

Added tests/test_worker_submission.py covering:
- Same-head resubmit from In Progress / Needs Human / Needs CI Fix reconciles lifecycle atomically, records the fresh summary, and rearms exactly one queue delivery (no spurious metadata write).
- Duplicate same-head submit already at Ready to Integrate is fully idempotent — zero tracker/queue writes.
- Cross-project isolation: reconciling one task does not mutate an unrelated project's queue row.

All 10 tests in test_worker_submission.py pass. Neighboring suites (integration_queue, integration_executor, task_handoff, submit_queue_concurrency, task_cli) all green.
---
<!-- COMMENTS:END -->
