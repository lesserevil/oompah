---
id: OOMPAH-532
type: task
status: In Validation
priority: 2
title: Apply duplicate-preflight verdicts without implementation transitions
parent: OOMPAH-528
children: []
blocked_by:
- OOMPAH-531
labels: []
assignee: null
created_at: '2026-07-28T21:19:28.624983Z'
updated_at: '2026-08-04T22:44:30.892296Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-216a219f736c
    project_id: proj-14849f1b
    task_id: OOMPAH-532
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f27213465bfff8140a3998693fe6a0a61a164e67cfd0816b12fc8ed672fb76f6
    attempts:
    - version: 1
      attempt_id: attempt-9ea66d0519c5
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f27213465bfff8140a3998693fe6a0a61a164e67cfd0816b12fc8ed672fb76f6
      created_at: '2026-08-04T22:42:07.443185+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T22:42:07.443185+00:00'
      branch_key: OOMPAH-532
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T22:36:46.855034+00:00'
    updated_at: '2026-08-04T22:42:07.443185+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-9ea66d0519c5
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f27213465bfff8140a3998693fe6a0a61a164e67cfd0816b12fc8ed672fb76f6
    created_at: '2026-08-04T22:42:07.443185+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T22:42:07.443185+00:00'
    branch_key: OOMPAH-532
oompah.task_costs:
  total_input_tokens: 13
  total_output_tokens: 80
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 13
      output_tokens: 80
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 13
    output_tokens: 80
    cost_usd: 0.0
    recorded_at: '2026-08-04T22:44:28.563138+00:00'
---
## Summary

Wire duplicate_detector worker completion into the preflight claim/evidence lifecycle from OOMPAH-529 through OOMPAH-531. Separate preflight completion from the existing normal focus handoff path.

Implementation scope:
- Extend the duplicate_detector prompt/run contract to return a structured verdict: no_duplicate, duplicate_candidate, or inconclusive, plus matched active task IDs and concise evidence. Validate the result before applying it.
- For no_duplicate, verify claim ID, detector version, and current task fingerprint; persist a checked pass, release the claim, keep status Open, and make the task eligible for a real implementation agent on a later selection step.
- For duplicate_candidate, verify that every referenced match is still non-terminal and accessible. Persist the verdict, move the task to Duplicate Candidate, and post one actionable evidence comment linking the canonical task(s).
- For inconclusive, malformed output, worker failure, timeout, or unavailable referenced task, release/expire the claim and leave the task Open and unchecked/stale for retry. Apply bounded retry/backoff so a poison task does not consume every tick; after the existing retry threshold, move it to Needs Human only with a final comment containing a concrete question or instruction for the human.
- Do not add focus-complete:duplicate_detector as the source of truth for preflight. Preserve compatibility for normal legacy focus handoffs until they can be safely retired.
- Ensure late worker completion after task edits, timeout, or a replacement claim cannot alter the new task revision or claim.
- Trigger a scheduling wake-up after a valid pass so newly implementation-eligible work need not wait for an unrelated event.

Relevant context/files:
- oompah/orchestrator.py worker exit/completion and _handoff_completed_focus paths.
- oompah/focus.py duplicate_detector instructions.
- Existing agent result/parsing patterns in auditor or structured focus handling.
- tests/test_orchestrator_duplicate_detection.py for EXOCOMP-55 and focus handoff regressions.

Required tests:
- All three structured verdicts and malformed output.
- A no-duplicate result remains Open, writes current evidence, releases the claim, and wakes dispatch.
- A supported active duplicate moves to Duplicate Candidate with exactly one evidence comment.
- A referenced terminal match is rejected and does not mark the source task duplicate.
- Timeout/retry/backoff and Needs Human escalation include human-actionable final comments.
- Late/stale/wrong-claim completion is a no-op except safe cleanup/logging.
- Legacy normal-focus behavior still passes existing regressions.

Acceptance criteria:
1. Preflight completion never falsely presents screening as implementation work.
2. Only a verified current pass unlocks real implementation dispatch.
3. Only active, verified matches can produce Duplicate Candidate.
4. Failure recovery is bounded, retryable, and compliant with Needs Human comment requirements.
5. Focused completion and regression tests pass through the appropriate Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 21:43
---
Claimed by the current interactive Codex session before OOMPAH-531 completion. Verdict handling is included in the pushed epic branch; do not dispatch another agent.
---
author: oompah
created: 2026-07-28 21:43
---
Implemented and pushed in 7a2e467fb: structured verdict contract, active-target verification, Open-state no-duplicate completion, Duplicate Candidate routing, stale/late no-op handling, bounded backoff, actionable Needs Human escalation, and immediate dispatch wake-up. Focused verdict regressions pass.
---
author: oompah
created: 2026-07-28 21:43
---
Verified duplicate-preflight completion lifecycle implemented and pushed in 7a2e467fb.
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
created: 2026-08-04 22:36
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 22:42
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 22:42
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 22:44
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 2
- Tokens: 13 in / 80 out [93 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 19s
- Log: OOMPAH-532__20260804T224226Z.jsonl
---
<!-- COMMENTS:END -->
