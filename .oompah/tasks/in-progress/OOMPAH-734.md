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
assignee: null
created_at: '2026-08-03T19:06:11.095695Z'
updated_at: '2026-08-03T19:18:42.046514Z'
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
oompah.agent_run_id: 5bd28ab1-184c-445a-bbcb-c92ac1b2ec66
oompah.task_costs:
  total_input_tokens: 50274
  total_output_tokens: 2145
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 50274
      output_tokens: 2145
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
<!-- COMMENTS:END -->
