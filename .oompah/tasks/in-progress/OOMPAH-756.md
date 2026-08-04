---
id: OOMPAH-756
type: bug
status: In Progress
priority: 1
title: Reconcile already-landed nested epics from In Review
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T11:07:47.294756Z'
updated_at: '2026-08-04T11:12:33.435354Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d89af1c468e2957d88adc6c1ed1ca4f822c1739f339ee7236032fa6b1c81379e
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T11:09:31.726742+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Closest reviewed tasks were OOMPAH-162 and OOMPAH-165,\
    \ but both are terminal Archived tasks and therefore cannot be duplicate targets.\
    \ No active peer task in the supplied corpus covers this specific nested-epic\
    \ In Review reconciliation bug.\nFocus handoff: duplicate_detector  \nDuplicate\
    \ preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence: Closest reviewed\
    \ tasks were OOMPAH-162 and OOMPAH-165, but both are terminal Archived tasks and\
    \ therefore cannot be duplicate targets. No active peer task in the supplied corpus\
    \ covers this specific nested-epic In Review reconciliation bug."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 03a9911e-996a-424a-9054-f597f3f07002
oompah.task_costs:
  total_input_tokens: 47084
  total_output_tokens: 233
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 47084
      output_tokens: 233
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 47084
    output_tokens: 233
    cost_usd: 0.0
    recorded_at: '2026-08-04T11:09:30.492180+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-756__20260804T110911Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-756
    source_sha: 5368e23617a98569caf7370b0f2eb63d41c8ba6b
    completed_at: '2026-08-04T11:09:30.502464+00:00'
---
## Summary

Triggered by: EXOCOMP-128

Regression/incomplete implementation of OOMPAH-748 on live revision 5368e236. EXOCOMP-128 remains In Review with no open review even though GitHub PR 21 merged epic-EXOCOMP-128 into its authoritative immediate target epic-EXOCOMP-127 at merge commit 2476a39252e92b4690337d7fe706d1b28781bd60, that merge commit is reachable from origin/epic-EXOCOMP-127, and multiple independent terminal auditors previously returned PASS for Merged. OOMPAH-748 head d4282363 is live, but it changed only _epic_auto_close_check. Existing nested epics already routed to In Review by the old lifecycle cycle do not naturally re-enter that auto-close path. The live scheduler instead repeatedly runs epic review readiness, reports historical child task branches as unverifiable, and defers EXOCOMP-128 as if a new review were needed, despite the authoritative merged review already existing. This continues to block parent EXOCOMP-127. Implementation scope: make merged-review and stale-In-Review reconciliation target-relative for nested epics; recognize an authoritative provider review whose source is the nested epic branch, target is the immediate parent branch, and merge commit is reachable from that parent; route terminal state through the coordinator using existing Done/Merged audit evidence or a fresh bounded audit; do not reopen a review or require deleted/private child branch refs after the epic review has landed; make restart reconciliation idempotent and preserve wrong-target, missing-merge, source-advanced, and premature-root protections. Relevant code: _epic_auto_close_check, _label_merged_epics, stale/deferred In Review reconciliation, _open_epic_main_prs readiness ordering, nested target resolution, terminal lifecycle coordinator, and provider review evidence. Required tests: exact EXOCOMP-128 restart state (In Review, merged PR to parent, merge reachable, prior passing audits); source branch present and deleted; historical child private refs absent; wrong target; merge not reachable; parent not yet on main; later parent landing; duplicate ticks/restarts. Acceptance criteria: a nested epic already landed on its immediate parent cannot remain In Review waiting for a new review or root-main landing; it reaches the target-relative audited terminal state and unblocks its parent, while root epics still cannot become Merged before main landing; focused epic, review reconciliation, audit lifecycle, and restart tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 11:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 11:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 11:09
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 47.1K in / 233 out [47.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 45s
- Log: OOMPAH-756__20260804T110911Z.jsonl
---
author: oompah
created: 2026-08-04 11:10
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 11:10
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-04 11:11
---
Task-specific recovery attempt: an authenticated project-owner terminal override to Merged was attempted for EXOCOMP-128 after independently confirming PR 21 target epic-EXOCOMP-127 and merge commit 2476a392 reachability. Live revision 5368e236 still rejected it with the old root-parent gate: 'parent epic EXOCOMP-127 could not be verified; parent review must land on its configured target branch first.' No tracker mutation occurred. This confirms the target-relative fix does not cover the terminal transition validator/override path; do not bypass it by editing task files.
---
author: oompah
created: 2026-08-04 11:12
---
UNDERSTANDING: This issue is about nested epics that have already merged to their immediate parent epic, but remain stuck in In Review state. OOMPAH-748 partially fixed this with target-relative auto-close validation, but didn't address reconciliation for epics already in In Review.

The core problem: nested epics in In Review don't naturally re-enter the auto-close validation path. The scheduler repeatedly runs review readiness checks instead, treating them as needing a new review despite the merged PR already existing.

PLAN:
1. Make merged-review reconciliation target-relative for nested epics (recognize PR with source=nested epic branch, target=immediate parent branch)
2. Implement stale In Review reconciliation to route terminal state through coordinator
3. Ensure don't reopen reviews or require deleted child branch refs after landing
4. Make reconciliation idempotent while preserving wrong-target, missing-merge, source-advanced, and premature-root protections
5. Add comprehensive tests for restart scenarios, branch presence/deletion, wrong targets, unreachable merges, and parent landing timing

RELEVANT CODE: orchestrator.py - _epic_auto_close_check, _label_merged_epics, review readiness, terminal_transition_coordinator, and nested target resolution
---
<!-- COMMENTS:END -->
