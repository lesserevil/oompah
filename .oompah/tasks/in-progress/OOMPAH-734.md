---
id: OOMPAH-734
type: bug
status: In Progress
priority: 1
title: Prevent auditor turn exhaustion after PASS from stranding terminal transitions
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- focus-complete:frontend
- focus-complete:docs
assignee: null
created_at: '2026-08-03T19:06:11.095695Z'
updated_at: '2026-08-03T20:08:24.257125Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: bef57ad9a792d097e5a56960af511f86d2370426c2d6472ae28549bd276dc6a3
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T19:10:27.396250+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed the supplied active project task corpus; no\
    \ non-terminal task addresses auditor turn exhaustion, commit-before-comment ordering,\
    \ terminal audit fencing, or duplicate auditor dispatch. Closest related tasks\
    \ are terminal and unrelated.\nFocus handoff: duplicate_detector  \nDuplicate\
    \ preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence: Reviewed the\
    \ supplied active project task corpus; no non-terminal task addresses auditor\
    \ turn exhaustion, commit-before-comment ordering, terminal audit fencing, or\
    \ duplicate auditor dispatch. Closest related tasks are terminal and unrelated."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 56ca178d-988a-4560-9989-7b52f9d11088
oompah.task_costs:
  total_input_tokens: 1381845
  total_output_tokens: 9577
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 51008
      output_tokens: 2320
      cost_usd: 0.0
    opus:
      input_tokens: 1330837
      output_tokens: 7257
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 50240
    output_tokens: 181
    cost_usd: 0.0
    recorded_at: '2026-08-03T19:10:27.395221+00:00'
  - profile: default
    model: haiku
    input_tokens: 34
    output_tokens: 1964
    cost_usd: 0.0
    recorded_at: '2026-08-03T19:12:49.596930+00:00'
  - profile: deep
    model: opus
    input_tokens: 1330837
    output_tokens: 7257
    cost_usd: 0.0
    recorded_at: '2026-08-03T19:18:57.180123+00:00'
  - profile: default
    model: haiku
    input_tokens: 734
    output_tokens: 175
    cost_usd: 0.0
    recorded_at: '2026-08-03T19:34:48.273481+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-734__20260803T190947Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-734
    source_sha: 806bf1feee8ac46220c8ec750a5167017834b176
    completed_at: '2026-08-03T19:10:27.411011+00:00'
  - run_id: OOMPAH-734__20260803T191430Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: frontend
    source_branch: OOMPAH-734
    source_sha: 561070d6c405563830c20d8569dfa543f0fd5832
    completed_at: '2026-08-03T19:18:57.184079+00:00'
---
## Summary

Triggered by: OOMPAH-729

Production regression observed on OOMPAH-729. Its first independent auditor reached the 100-turn ceiling after posting an Audit PASS — Done comment, but before the authoritative terminal result was committed. The task remained In Validation and the scheduler launched a redundant second auditor. An owner override was required to cancel that run and apply the already-supported terminal outcome.

Implementation scope:
- Reproduce an auditor reaching its configured turn ceiling after deciding PASS but before submitting the coordinator terminal result.
- Make the authoritative terminal-result commit occur before any human-readable PASS or FAIL comment, or otherwise reserve a non-starvable finalization path outside the model turn/tool budget.
- Ensure a provider exit, timeout, or policy denial cannot leave a misleading PASS comment while the durable audit remains In Progress.
- Preserve fail-closed authority: never infer a terminal result from comment text alone.
- Ensure a committed PASS atomically retires same-target/same-fingerprint sibling audits and prevents redispatch.
- Ensure an owner override or other authority revocation promptly retires the redundant auditor process and its persisted attempt.
- Add observability that distinguishes an uncommitted verdict/finalization failure from provider transport and auditor command-policy failures.

Required tests:
- Boundary test where the auditor consumes its final ordinary turn while deciding PASS and still commits the terminal result exactly once.
- Crash ordering tests proving commit-before-comment recovery is idempotent and that comment-before-commit cannot occur.
- Scheduler race test proving no second auditor launches after a committed PASS for the same target and fingerprint.
- Exit-before-commit test proving the task remains fail-closed with an actionable finalization alert and no misleading PASS comment.
- Authority-revocation test proving the active auditor is stopped and cannot later overwrite the terminal decision.
- Focused terminal coordinator, audit scheduler, agent lifecycle, and dashboard health tests; run make test.

Acceptance criteria:
- An auditor that reaches its normal turn ceiling after reaching a verdict cannot strand the task in In Validation.
- Dashboard comments and tracker state cannot disagree by showing PASS — Done while the durable result is incomplete.
- Duplicate auditor dispatch is prevented or automatically retired without operator intervention.
- Terminal authority, fingerprint fencing, audit history, and independent-candidate requirements remain intact.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 19:09
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 19:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 19:10
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.2K in / 181 out [50.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 49s
- Log: OOMPAH-734__20260803T190947Z.jsonl
---
author: oompah
created: 2026-08-03 19:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 19:11
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-03 19:12
---
HANDOFF: This issue requires backend infrastructure fixes, not frontend UI work. The core problem is commit ordering in the terminal coordinator and race conditions in the audit scheduler. Specifically needed:

1. **Terminal Coordinator**: Make terminal result commits atomic and ordered BEFORE any comment posting
2. **Audit Scheduler**: Prevent duplicate dispatch after committed PASS by checking durable state, not comment text
3. **Agent Lifecycle**: Handle turn exhaustion correctly - auditor must commit terminal result even when reaching turn ceiling
4. **Recovery Path**: Ensure fail-closed behavior with actionable finalization alerts
5. **Tests**: Boundary tests, crash-ordering tests, scheduler race tests, authority-revocation tests

Relevant systems:
- Terminal coordinator (commit ordering and atomicity)
- Audit scheduler (dispatch logic and fingerprint fencing)
- Agent lifecycle (turn ceiling boundary conditions)
- Tracker state (durable vs. dashboard state consistency)

A backend specialist should take this task to implement the commit ordering fixes, scheduler logic, and comprehensive test coverage. Frontend work (if any dashboard changes are needed) can happen after the backend fix is complete and durable state is reliable.
---
author: oompah
created: 2026-08-03 19:12
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 9, Tool calls: 3
- Tokens: 34 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 42s
- Log: OOMPAH-734__20260803T191114Z.jsonl
---
author: oompah
created: 2026-08-03 19:14
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-03 19:14
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-03 19:15
---
Understanding: The production regression is a backend durability and lifecycle issue: the authoritative audit result must commit before any PASS/FAIL comment, survive the final ordinary auditor turn, fence duplicate dispatch, and honor authority revocation. In this frontend focus I will verify whether any dashboard presentation code is implicated; if not, I will record a frontend focus handoff with concrete backend scope and routing.
---
author: oompah
created: 2026-08-03 19:15
---
Discovery: The authoritative path is entirely backend (, , and auditor exit handling in ). The dashboard already renders server-supplied alerts generically and separately summarizes launch/transport and local command-policy failures, but it has no distinct summary fact for an uncommitted verdict/finalization failure. I will add that forward-compatible frontend health fact and focused contract coverage, then hand off the durable-state/lifecycle implementation.
---
author: oompah
created: 2026-08-03 19:16
---
Discovery correction: The authoritative path is entirely backend in oompah/terminal_transition_coordinator.py, oompah/auditor_dispatch.py, and auditor exit handling in oompah/orchestrator.py. The dashboard already renders server-supplied alerts generically and separately summarizes launch/transport and local command-policy failures, but it has no distinct summary fact for an uncommitted verdict/finalization failure. I will add that forward-compatible frontend health fact and focused contract coverage, then hand off the durable-state/lifecycle implementation.
---
author: oompah
created: 2026-08-03 19:17
---
Implementation: Updated the dashboard terminal-audit health summary to render a dedicated finalization_failure_count as uncommitted audit finalization failures, keeping it visibly distinct from provider launch/transport and local command-policy failures. Added focused dashboard contract coverage for the new fact and wording. The frontend is forward-compatible with the backend health payload still to be implemented.
---
author: oompah
created: 2026-08-03 19:17
---
Verification: Focused dashboard health suite passed: 20 tests in tests/test_dashboard_terminal_audit_health.py. git diff --check passed. make test-setup could not run because the sandboxed Snap uv launcher failed with cannot create transient scope; the self-contained focused suite was run with the available pytest runtime instead. Full make test is deferred to the orchestrator's complete branch gate after backend implementation.
---
author: oompah
created: 2026-08-03 19:18
---
Focus handoff: frontend

Outcome: Added the user-facing observability slice and pushed commit 561070d6c. The terminal-audit health banner now presents finalization_failure_count as uncommitted audit finalization failures, distinct from provider launch/transport and local auditor command-policy failures.

Relevant files and evidence: oompah/templates/dashboard.html and tests/test_dashboard_terminal_audit_health.py. Focused test command python3 -m pytest tests/test_dashboard_terminal_audit_health.py -q passed 20 tests; git diff --check passed. make test-setup was blocked by the sandboxed Snap uv transient-scope failure, so the self-contained suite used the available pytest runtime.

Remaining work and risks: Backend must add and populate the durable finalization_failure_count health fact and alert source; commit the structured verdict before any PASS/FAIL comment; provide a non-starvable finalization path at the turn ceiling; keep exit-before-commit fail-closed; fence same-target/same-fingerprint sibling dispatch; terminate persisted/running auditors on authority revocation; and add the required coordinator, scheduler, lifecycle, health, crash-ordering, race, and revocation tests. The frontend intentionally does not infer outcomes from comments.

Recommended next focus: backend/feature implementation in terminal_transition_coordinator.py, auditor_dispatch.py, orchestrator.py, terminal_audit_health.py, and their focused test suites. Preserve the existing needs:backend routing.
---
author: oompah
created: 2026-08-03 19:18
---
Agent completed successfully in 275s (1338094 tokens)
---
author: oompah
created: 2026-08-03 19:18
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 34
- Tokens: 1.3M in / 7.3K out [1.3M total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 35s
- Log: OOMPAH-734__20260803T191430Z.jsonl
---
author: oompah
created: 2026-08-03 19:19
---
Focus handoff from `frontend` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-08-03 19:20
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 19:20
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-03 19:24
---
Understanding: The production regression stems from improper commit ordering in the terminal coordinator and auditor lifecycle boundary conditions. The frontend observability work is complete; the backend design docs (terminal-transition-coordinator.md, independent-auditor-dispatch.md) exist but need clarification about:

1. **Commit-before-comment ordering**: Durable terminal result must persist before any human-readable PASS/FAIL comment
2. **Turn-ceiling boundary handling**: Auditor must reserve a non-starvable finalization path for the result commit after its final ordinary turn
3. **Duplicate-dispatch prevention**: Committed PASS must fence same-target/same-fingerprint sibling audits via fingerprint check in scheduler
4. **Exit-before-commit fail-closed**: Provider exit/timeout cannot leave misleading PASS comment while durable audit remains incomplete

I will update the design docs to make the commit ordering and turn-ceiling requirements explicit for the backend implementation, then hand off to a backend specialist.
---
author: oompah
created: 2026-08-03 19:31
---
Discovery: The issue stems from incorrect commit ordering: the auditor posts a PASS comment before the coordinator persists the durable verdict, leaving the task in In Validation when the auditor hits its turn ceiling. I have updated three design documents to specify the required fix:

1. **plans/terminal-transition-coordinator.md** — Added 'Commit-Before-Comment Ordering' section:
   - Verdict record MUST be persisted as COMPLETED before any tracker comment
   - Provides recovery path for exit-before-comment scenarios
   - Clarifies turn-ceiling boundary: finalization call is non-starvable, outside ordinary turn budget
   - Ensures no auditor can strand the task by reaching its turn limit

2. **plans/independent-auditor-dispatch.md** — Added 'Turn-Ceiling and Finalization Semantics':
   - Auditor reserves finalization call outside turn budget
   - Turn N-1: complete logic and decide verdict; Turn N: invoke submit_audit_result non-starvably
   - Added 'Fingerprint-Based Duplicate-Dispatch Prevention' section explaining how committed PASS prevents second auditor via compare-and-set

3. **docs/auditor-dispatch-operations.md** — Added 'Uncommitted Finalization Failures' troubleshooting:
   - Operator-facing recovery guidance for finalization failures
   - Auto-recovery on restart; manual rearm command if needed

These docs now prescribe the exact requirements for backend implementation.
---
author: oompah
created: 2026-08-03 19:33
---
Focus handoff: docs

Outcome: Updated design and operator documentation to prescribe the commit-before-comment ordering and turn-ceiling boundary handling required to fix OOMPAH-734. The frontend observability (finalization_failure_count) is already complete and ready to display backend-provided health data.

Relevant files and evidence: 
- plans/terminal-transition-coordinator.md: Added Commit-Before-Comment Ordering section with sequence, recovery path, and turn-ceiling boundary details
- plans/independent-auditor-dispatch.md: Added Turn-Ceiling and Finalization Semantics section + Fingerprint-Based Duplicate-Dispatch Prevention section
- docs/auditor-dispatch-operations.md: Added Uncommitted Finalization Failures troubleshooting with recovery procedures

Commit: 73efb9333 (OOMPAH-734: Document commit-before-comment ordering and turn-ceiling requirements)

Remaining work and risks: Backend must implement:
1. Terminal result atomically persisted as COMPLETED before posting tracker comment (terminal-transition-coordinator.py apply_audit_result method)
2. Auditor finalization call reserved outside turn budget (orchestrator/auditor lifecycle)
3. Duplicate dispatch prevention via fingerprint check in scheduler before launch (auditor_dispatch.py)
4. Exit-before-commit recovery path to reapply persisted verdicts on restart (terminal_transition_coordinator.py startup)
5. Required test coverage: boundary test (auditor at turn ceiling still commits), crash-ordering tests, scheduler race test, exit-before-commit test, authority-revocation test
6. Backend health endpoint must provide finalization_failure_count for dashboard

Recommended next focus: backend/feature implementation. Start with the implemented terminal-transition-coordinator design to understand the compare-and-set result validation contract, then implement commit-before-comment ordering in apply_audit_result. Preserve needs:backend routing.
---
author: oompah
created: 2026-08-03 19:34
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 39
- Tokens: 734 in / 175 out [909 total]
- Cost: $0.0000
- Exit: terminated, Duration: 14m 28s
- Log: OOMPAH-734__20260803T192031Z.jsonl
---
author: oompah
created: 2026-08-03 20:08
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 20:08
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->
