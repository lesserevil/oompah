---
id: OOMPAH-684
type: task
status: Ready to Integrate
priority: null
title: Prevent stale retry dispatch after operator task resubmission
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T21:44:29.390457Z'
updated_at: '2026-08-01T22:48:00.393190Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 57d3415e0f3269957b9627d45a447cc345e9142b40cdb196449e066c34db7fe9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T21:52:20.259619+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation, I can now provide my findings\
    \ on the duplicate status of OOMPAH-684.\n\n## Investigation Summary\n\nI have\
    \ conducted a thorough search across all task states, documentation, plans, and\
    \ the codebase:\n\n**Search Coverage:**\n- `.oompah/tasks/` directory across all\
    \ states (merged/, archived/, open/, backlog/)\n- Documentation (`docs/`) and\
    \ plans (`plans/`) directories\n- External imports registry\n- Codebase for references\
    \ to retry dispatch, task submission, and generation authority\n\n**Key Findings:**\n\
    \n1. **OOMPAH-661 does not exist** in the current task tracker (neither merged/,\
    \ archived/, open/, nor external imports). The issue description refers to it\
    \ as \"merged,\" but it's not present in the system.\n\n2. **No active task addresses\
    \ the same problem**: I found no open, in-progress, or merged task covering:\n\
    \   - Stale retry dispatch after operator task resubmission\n   - Generation-authority\
    \ invariant for task dispatch\n   - Race conditions between task CLI submit and\
    \ worker dispatch\n   - Ready to Integrate state protection against stale retry\
    \ authority\n   - Atomic cancellation of retries upon successful operator resubmission\n\
    \n3. **Related but distinct tasks** that use \"retry\" involve different systems:\n\
    \   - OOMPAH-211 (Archived): Comment delivery to running agents (different scope)\n\
    \   - OOMPAH-179, OOMPAH-216 (Archived): Release delivery PR polling and retry/archive\
    \ (release delivery system, not task dispatch)\n   - OOMPAH-265 (Archived): Git\
    \ push-race recovery with retries (git infrastructure, not task dispatch)\n  \
    \ - OOMPAH-270 (Archived): Git lock error retries (transient git failures, not\
    \ task authority)\n\n4. **Searched keywords**: \"dispatch\", \"retry\", \"submit\"\
    , \"operator\", \"resubmit\", \"generation\", \"authority\", \"Ready to Integrate\"\
    , \"stale\" \u2014 no matches in active task descriptions or titles that cover\
    \ OOMPAH-684's specific race condition.\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matche"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d063adb7-80fe-42ac-b8f3-60b0eee801b9
oompah.task_costs:
  total_input_tokens: 202
  total_output_tokens: 6472
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 202
      output_tokens: 6472
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 202
    output_tokens: 6472
    cost_usd: 0.0
    recorded_at: '2026-08-01T21:52:20.254020+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-684__20260801T214746Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-684
    source_sha: 3d50e86c334e8a6318b767b281bc254fa6d93cc2
    completed_at: '2026-08-01T21:52:20.275034+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-684
  head_sha: bfcd6f1999dc6739d37c28ef481bce29aee08527
  submitted_at: '2026-08-01T22:47:56.761772+00:00'
  updated_at: '2026-08-01T22:47:56.761772+00:00'
---
## Summary

Regression of merged OOMPAH-661 observed on NODEVIRT-7 on 2026-08-01. An operator recovered the preserved worktree, committed validated head bb916af, pushed the assigned branch, and successfully submitted it through the operator-authenticated task CLI. The task entered Ready to Integrate. Roughly three minutes later, stale retry/assignment authority launched implementation run e84dc6296e524e23ac0255bfb692c480 and rewrote the canonical task to In Progress with integration state working, despite the accepted head already being pushed and queued. The redundant worker initially performed only read-only inspection; an operator live handoff told it not to mutate the accepted branch.

This is a direct recurrence of the generation-authority invariant from OOMPAH-661 and must be fixed at the race boundary rather than special-cased.

Implementation scope:
- Trace operator CLI submit through api_submit_issue, native Markdown tracker persistence, retry cancellation, refresh/event coalescing, claimed/running state, and due retry dispatch to identify how stale authority survived.
- Make accepted submission and retry/claim cancellation one atomic authority transition for the exact task generation. A due callback or candidate selected before submission must re-read and reject Ready to Integrate, matching integration metadata/head, replacement assignment, or changed tracker updated_at before it writes In Progress or launches a worker.
- Fence already-starting dispatch setup so a submit that wins before provider launch cancels setup and removes the running/claimed row without tracker rollback.
- If a worker process crosses the boundary, terminate or quarantine it before repository mutation and preserve the accepted Ready to Integrate generation.
- Ensure same-head operator resubmission from Needs Human exercises identical cancellation semantics to a first worker submission.
- Add observability identifying which authority generation lost the race without exposing tokens.

Relevant code: retry authority generation and persisted retries, normal dispatch claim/setup, worker assignment metadata, api_submit_issue/task CLI submission reconciliation, native tracker cache/update ordering, running state, and event-driven refresh.

Required deterministic tests:
- Failed/Needs Human native task is operator-resubmitted at a pushed head while a due retry callback is selected; only Ready to Integrate survives and no worker launches.
- Submit wins during dispatch setup before provider launch; setup aborts without writing In Progress.
- Provider launch crossing the boundary cannot mutate the worktree and accepted head/status are restored automatically.
- Same-head resubmission clears retrying, claimed, running placeholder, integration working metadata, and stale assignment atomically.
- Restart/event coalescing cannot rehydrate the withdrawn retry.
- Unrelated tasks and legitimate post-rejection retries remain unaffected.

Acceptance criteria:
- The exact NODEVIRT-7 sequence cannot redispatch after successful resubmission.
- Ready to Integrate head/status/integration metadata remain authoritative through all tested interleavings.
- Focused retry/submission/dispatch race tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 21:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 21:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 21:52
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 83, Tool calls: 35
- Tokens: 202 in / 6.5K out [6.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 44s
- Log: OOMPAH-684__20260801T214746Z.jsonl
---
author: oompah
created: 2026-08-01 21:53
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 21:53
---
Focus: Callback Auth Validation Specialist
---
author: oompah
created: 2026-08-01 21:53
---
Understanding: stale retry dispatch is surviving operator submission across retry, claim/running, tracker persistence, and event refresh boundaries. I will trace the submission and dispatch paths, identify the shared generation authority transition, add an atomic stale-callback fence and setup/worker quarantine behavior, then cover the listed race interleavings with deterministic tests.
---
author: oompah
created: 2026-08-01 21:57
---
Discovery: _on_retry_timer retains a retry entry during refresh, but _dispatch writes In Progress before its final retry CAS. _cancel_retry_for_issue removes claimed but not claimed_issues and does not quarantine a registered worker. Parallel-epic workspace setup can persist oompah.integration=working before provider launch. The fix will share the per-task transition lock with submission, revoke exact generations, clear claim placeholders, quarantine live workers, and gate workspace metadata writes on live authority.
---
author: oompah
created: 2026-08-01 22:15
---
Implementation: operator submission now shares the per-task transition lock with retry dispatch, revokes exact retry/running generations, clears claimed placeholders and stale assignment metadata, and quarantines workers that cross the acceptance boundary. Workspace/integration setup mutations are authority-guarded; withdrawn shared claims are conditionally removed by run ID. Added deterministic tests for setup cancellation, running-worker quarantine, claim cleanup, and same-head resubmission.
---
author: oompah
created: 2026-08-01 22:23
---
Oompah could not durably preserve this worker's task worktree before retry. The worktree was left in place and no reset, clean, or retry was started. Reconcile the workspace and recovery evidence manually before resuming the task. Error: could not stage recovery snapshot for OOMPAH-684: The following paths are ignored by one of your .gitignore files:
.oompah-no-hooks
hint: Use -f if you really want to add them.
hint: Disable this message with "git config set advice.addIgnoredFile false"
---
author: oompah
created: 2026-08-01 22:47
---
Operator-owned recovery complete at bfcd6f1999dc6739d37c28ef481bce29aee08527. The stale dispatch implementation was preserved, reviewed, committed, and pushed after removing only the generated .oompah-no-hooks helper.\n\nValidation:\n- Focused retry-authority and worker-submission suites: 32 passed.\n- Full make test: 14859 passed, 7 skipped, 1 xfailed in 410.24s.\n- git diff --check passed.\n- Branch is clean and matches origin/OOMPAH-684.\n\nThe Needs Human transition was caused by the ignored generated-helper snapshot defect already fixed canonically by OOMPAH-683; no duplicate follow-up was filed.
---
author: oompah
created: 2026-08-01 22:48
---
Operator recovery complete at bfcd6f199: submission now atomically revokes retry/run authority, clears stale claims, fences workspace mutations, and quarantines crossed workers; focused 32/32 and full 14859-test gates pass.
---
<!-- COMMENTS:END -->
