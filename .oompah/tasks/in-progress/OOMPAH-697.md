---
id: OOMPAH-697
type: bug
status: In Progress
priority: 1
title: Requeue branches that advance after their recorded review merges
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T16:21:00.027506Z'
updated_at: '2026-08-02T16:23:54.546803Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3d4dcd1225d01ef9a3fa6c3277b48ee6432c055f7096368737892a5afa9b5bf8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-02T16:23:01.957663+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Active tasks OOMPAH-281 and OOMPAH-282 are unrelated.\
    \ Closest reviewed terminal tasks\u2014OOMPAH-216, OOMPAH-179, OOMPAH-195, OOMPAH-202,\
    \ and OOMPAH-235\u2014address release-delivery polling or tracker-write races,\
    \ not requeuing newer branch heads after merged reviews."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 419b479d-f9e7-4142-85da-5c920d2cd5aa
oompah.task_costs:
  total_input_tokens: 631109
  total_output_tokens: 2505
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 631109
      output_tokens: 2505
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 631109
    output_tokens: 2505
    cost_usd: 0.0
    recorded_at: '2026-08-02T16:23:01.954879+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-697__20260802T162155Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-697
    source_sha: b7fdf2b3f6dfa00f39659abafb176f3d67579dce
    completed_at: '2026-08-02T16:23:01.976548+00:00'
---
## Summary

Triggered by: OOMPAH-680

Observed production failure on OOMPAH-680 and OOMPAH-682: each task is shown as In Review while the live review cache and forge report zero open reviews. PR #643 and PR #645 merged successfully, but each task branch later advanced by one commit (OOMPAH-680 head d08a8da59; OOMPAH-682 head 71f87859f). Neither current head is an ancestor of main and neither has a new PR. The task metadata retained the obsolete merged review, so reconciliation routed the newer branch generation to In Review instead of running the normal exact-head gate and opening a fresh review.

Implementation scope:
- In standalone review creation and _reconcile_stale_in_review_tasks, bind review evidence to the exact source branch head/generation it reviewed, not only branch name or persisted review_url/review_number.
- Treat a recorded review that is merged or closed at an older head as historical evidence, never as an active review for a newer branch head.
- When the current remote branch is ahead of the reviewed/merged head and not contained in the target branch, clear or supersede active review metadata, restore the task to Ready to Integrate, run the exact-head branch quality gate, and create a new PR/MR through the normal capacity-controlled path.
- Ensure reviews_summary/open_reviews_by_project and the In Review task state agree: a task may remain In Review only when the forge has a currently open review covering its current submitted head.
- Preserve old review history for auditability, handle webhook/poll races idempotently, and avoid duplicate PR creation when a current-head review already exists.

Relevant code: oompah/orchestrator.py _ensure_review_exists, _reconcile_stale_in_review_tasks, standalone Ready-to-Integrate delivery/review metadata persistence, forge review lookup helpers, and tests/test_orchestrator_merged.py plus review/quality-gate tests.

Required tests:
- Reproduce OOMPAH-680: old PR merged, branch advances one commit, stale review metadata exists; reconciliation returns the task to integration, gates the new SHA, opens one new review, and refreshes active review metadata.
- Reproduce OOMPAH-682 with recovery/resubmission metadata and prove the same outcome.
- A merged review whose reviewed head is already in main remains terminal and does not reopen.
- An open review at the exact current head remains In Review and no duplicate is created.
- Closed-unmerged, merged-old-head, webhook-lag, restart, and concurrent reconciliation paths remain idempotent.
- Dashboard review counts and task lifecycle cannot disagree after reconciliation.

Acceptance criteria:
- OOMPAH-680 and OOMPAH-682 cannot remain In Review with zero active forge reviews while their current heads are unmerged.
- Every post-merge branch advance receives fresh exact-head gate evidence and a new review before it can return to In Review.
- Stale merged review metadata cannot strand future branch generations or cause duplicate reviews.
- Focused review/reconciliation tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 16:21
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 16:21
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 16:23
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 10
- Tokens: 631.1K in / 2.5K out [633.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 18s
- Log: OOMPAH-697__20260802T162155Z.jsonl
---
author: oompah
created: 2026-08-02 16:23
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-02 16:23
---
Focus: Callback Auth Validation Specialist
---
author: oompah
created: 2026-08-02 16:23
---
## Understanding

**Issue Summary:** Tasks remain in 'In Review' state with zero active forge reviews when:
1. A PR merged successfully (e.g., PR #643 for OOMPAH-680)
2. The task branch later advances by a new commit (head changed from old SHA to new SHA)
3. Task metadata still holds the old (merged) review_url/review_number
4. Reconciliation wrongly treats this stale review as active and keeps task in In Review instead of requeuing

**Root Cause:** Current code treats reviews by branch name only, not by the exact head/generation they reviewed. Once the branch head advances past what was reviewed, the old review is obsolete but still blocks integration.

**Planned Approach:**
1. Explore orchestrator.py to understand current review binding logic
2. Find where review metadata is persisted and checked
3. Modify review evidence binding to include exact head/generation
4. Update reconciliation to detect when current head exceeds reviewed head
5. Clear stale review metadata and restore task to Ready when needed
6. Add tests reproducing OOMPAH-680 scenario and confirming recovery behavior

**My Focus:** As Callback Auth specialist, I'll pay attention to event handling idempotency, webhook race conditions, and proper state consistency in recovery paths.
---
<!-- COMMENTS:END -->
