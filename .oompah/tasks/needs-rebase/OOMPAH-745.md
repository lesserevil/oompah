---
id: OOMPAH-745
type: task
status: Needs Rebase
priority: 1
title: Add browser-level alert density and recovery regression coverage
parent: OOMPAH-740
children: []
blocked_by:
- OOMPAH-742
- OOMPAH-743
- OOMPAH-744
start_blocked_by: []
labels:
- focus-complete:merge_conflict
assignee: null
created_at: '2026-08-03T22:56:27.836890Z'
updated_at: '2026-08-04T15:36:28.471441Z'
work_branch: epic-OOMPAH-740--task-OOMPAH-745
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7ea5e0154cb84e897e182323a5c5ecb62c34b8624fe7e160c8ad4160013fc8d1
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T23:11:08.721622+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-745 describes a dedicated integration/regression\
    \ testing task that validates the *combined* alert experience under production-like\
    \ conditions \u2014 covering browser viewports, accessibility, recovery convergence,\
    \ layout bounds, and mixed payloads. The four active non-terminal peers in the\
    \ same epic are each implementation tasks with narrower, complementary scope:\n\
    Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\n\nEvidence: OOMPAH-745 describes a dedicated integration/regression\
    \ testing task that validates the *combined* alert experience under production-like\
    \ conditions \u2014 covering browser viewports, accessibility, recovery convergence,\
    \ layout bounds, and mixed payloads. The four active non-terminal peers in the\
    \ same epic are each implementation tasks with narrower, complementary scope:\n\
    \n- **OOMPAH-741** (In Progress) \u2014 server-side actionability contract: defines\
    \ structured alert fields and producer behavior; its tests cover producers and\
    \ snapshot construction, not browser-level harness integration.\n- **OOMPAH-742**\
    \ (Open) \u2014 UI implementation: replaces stacked banners with a compact alert\
    \ center; its required tests are scoped to that UI feature's own rendering states\
    \ (no/one/many alerts, collapse/expand), not the full production-payload combination\
    \ or accessibility suite that OOMPAH-745 describes.\n- **OOMPAH-743** (Open) \u2014\
    \ transcript sanitization: enforces length limits and redaction at both producer\
    \ and renderer boundaries; its tests cover sanitization correctness, not full-resync\
    \ convergence or viewport layout measurements.\n- **OOMPAH-744** (Open) \u2014\
    \ atomic stale-alert clearing: fixes the DOM lifecycle on WebSocket resync; its\
    \ tests cover specific convergence transitions, not the breadth of scenarios in\
    \ OOMPAH-745's acceptance criteria.\n\nOOMPAH-745 explicitly lists OOMPAH-742,\
    \ OOMPAH-743, and OOMPAH-744 as blockers, confirming it is the downstream integration\
    \ harness that proves the sibling implementations work correctly together. No\
    \ other active task in the corpus covers that role. All similarity-selected candidates\
    \ are Archived (terminal) and therefore excluded as duplicate targets. No active\
    \ duplicate exists."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-740--task-OOMPAH-745
oompah.integration:
  version: 2
  state: blocked
  attempts: 1
  task_branch: epic-OOMPAH-740--task-OOMPAH-745
  base_branch: epic-OOMPAH-740
  base_sha: b51047023a5a9d5a36d119260222fb57168cbf41
  head_sha: 2361ecf83000d89fdf37ff9d088954231c18db4c
  submitted_at: '2026-08-04T00:08:33.005683+00:00'
  updated_at: '2026-08-04T15:36:21.947813+00:00'
  last_error: 'Rebase onto the latest epic head conflicted: warning: skipped previously
    applied commit b9030acc4

    hint: use --reapply-cherry-picks to include skipped commits

    hint: Disable this message with "git config set advice.skippedCherryPicks false"

    Rebasing (1/3)

    error: could not apply 4da252e6a... OOMPAH-743: Bound dashboard alert failure
    transcripts

    hint: Resolve all conflicts manually, mark them as resolved with

    hint: "git add/rm <conflicted_files>", then run "git rebase --continue".

    hint: You can instead skip this commit: run "git rebase --skip".

    hint: To abort and get back to the state before "git rebase", run "git rebase
    --abort".

    hint: Disable this message with "git config set advice.mergeConflict false"

    Could not apply 4da252e6a... # OOMPAH-743: Bound dashboard alert failure transcripts'
oompah.task_costs:
  total_input_tokens: 6
  total_output_tokens: 1156
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 6
      output_tokens: 1156
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 3
    output_tokens: 513
    cost_usd: 0.0
    recorded_at: '2026-08-03T23:11:08.719654+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 3
    output_tokens: 643
    cost_usd: 0.0
    recorded_at: '2026-08-03T23:42:09.430561+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-745__20260803T230737Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: sonnet
    focus: duplicate_detector
    source_branch: epic-OOMPAH-740--task-OOMPAH-745
    source_sha: 583fb236963493a820f36eabdd29789fa5497e6b
    completed_at: '2026-08-03T23:11:08.738254+00:00'
  - run_id: OOMPAH-745__20260803T231904Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: sonnet
    focus: merge_conflict
    source_branch: epic-OOMPAH-740--task-OOMPAH-745
    source_sha: 583fb236963493a820f36eabdd29789fa5497e6b
    completed_at: '2026-08-03T23:42:09.434774+00:00'
---
## Summary

Add deterministic integration coverage proving that the complete alert experience remains compact, truthful, accessible, and convergent under production-like combinations of facts.

Scope:
- Extend the existing dashboard and WebSocket browser harnesses with representative alert payloads for integration rebase conflict, stale audit backlog, recovered auditor transport failure, running and failed quality gates, healthy repository hygiene, authentication policy denial, and genuine operator-actionable failures.
- Exercise a common desktop viewport matching the production screenshot and smaller responsive sizes.
- Verify initial load, incremental update, sequence-gap full resync, expand and collapse, many-alert overflow, task navigation, and recovery clearing.
- Assert semantic outcomes rather than fragile pixel snapshots where possible, while adding bounded layout measurements for alert-center height and board visibility.
- Include accessibility checks for disclosure state, focus order, alert announcements, and details access.
- Document any intentional presentation contract in existing user-facing dashboard documentation if operator behavior changes.

Relevant files: dashboard UI tests, WebSocket lifecycle and convergence tests, Granian end-to-end fixtures where applicable, and existing dashboard documentation.

Required tests and acceptance criteria:
- With the production-like mixed payload, the collapsed alert center remains bounded and the Kanban board is visible at initial render.
- Each underlying actionable fact appears once.
- Normal and healthy facts stay out of the actionable list.
- Expanding exposes sanitized details within an internally scrollable region.
- Recovery and full resync remove stale warnings without reload.
- No raw transcript appears in always-visible text.
- The full make test gate passes on the exact review-ready head.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 23:07
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-08-03 23:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 23:11
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 4, Tool calls: 0
- Tokens: 3 in / 513 out [516 total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 49s
- Log: OOMPAH-745__20260803T230737Z.jsonl
---
author: oompah
created: 2026-08-03 23:18
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-03 23:19
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-08-03 23:33
---
Understanding (Merge Conflict Resolver): Branch epic-OOMPAH-740--task-OOMPAH-745 currently has no unique commits — it is at the same HEAD as origin/epic-OOMPAH-740 (583fb2369). There are no merge conflicts to resolve. My scope is to: (1) fetch + rebase onto origin/epic-OOMPAH-740 (will be a no-op), (2) push the branch to origin to establish remote tracking, and (3) hand off to an implementation agent with the 'test' focus, since the actual work (writing browser-level alert density and recovery regression tests) has not started. Note: this task is blocked by OOMPAH-742, OOMPAH-743, and OOMPAH-744 which are also in the same not-yet-implemented state.
---
author: oompah
created: 2026-08-03 23:40
---
Focus handoff: merge_conflict

**Outcome:** No conflicts found. The branch epic-OOMPAH-740--task-OOMPAH-745 had no unique commits — it was at the same HEAD as origin/epic-OOMPAH-740 (583fb2369). Rebase was a no-op. Branch has been pushed to origin to establish remote tracking.

**Evidence:**
- git fetch + git rebase origin/epic-OOMPAH-740 → 'Current branch is up to date'
- git push --force-with-lease -u origin → new branch pushed successfully
- git status → branch up to date with origin/epic-OOMPAH-740--task-OOMPAH-745, nothing to commit

**Relevant files for implementation:**
- tests/test_dashboard_credential_warning.py — primary pattern for dashboard JS static-analysis tests (parse HTML, extract JS functions, assert behavior)
- tests/test_ws_lifecycle.py — WebSocket mock infrastructure pattern
- tests/test_ws_full_sync.py and tests/test_ws_fault_injection.py — convergence/full-resync patterns
- oompah/templates/dashboard.html — lines 3275–3295 (renderAlertItem, renderAlertSummary), lines 3545–3620 (handleStateUpdate alert routing)
- Existing dashboard alert tests: test_dashboard_credential_warning.py, test_credential_error_alert.py, test_github_intake_alert_lifecycle.py

**Alert routing in dashboard.html:**
- cred_error: alerts → dedicated cred-error banner
- auth_health: alerts → auth-health banner  
- All other alerts → alerts-banner (#alerts-list) + agent-bar warnings inline
- renderAlertItem, renderAlertSummary, renderTerminalAuditHealth, renderQualityGateHealth, renderRepoHygieneHealth are the key rendering functions

**Remaining work:**
- Implement test_dashboard_alert_density.py (or extend existing test files) covering the scope in the task description: mixed payloads, bounded height assertions, actionable vs. normal fact filtering, expansion/collapse, recovery clearing, accessibility checks for disclosure state/focus order
- This task is blocked by OOMPAH-742, OOMPAH-743, OOMPAH-744 — those dependencies must be integrated before OOMPAH-745 can land

**Risks:**
- The sibling tasks (742, 743, 744) are also at origin/epic-OOMPAH-740 HEAD with no commits — all four tasks in the epic appear to be at the implementation starting point; coordination will be needed to avoid test file conflicts

**Recommended next focus:** test
---
author: oompah
created: 2026-08-03 23:42
---
Agent completed successfully in 1401s (646 tokens)
---
author: oompah
created: 2026-08-03 23:42
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 74, Tool calls: 48
- Tokens: 3 in / 643 out [646 total]
- Cost: $0.0000
- Exit: normal, Duration: 23m 21s
- Log: OOMPAH-745__20260803T231904Z.jsonl
---
author: oompah
created: 2026-08-03 23:42
---
Focus handoff from `merge_conflict` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-08-03 23:43
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-03 23:43
---
Focus: Test Engineer
---
author: oompah
created: 2026-08-03 23:44
---
Understanding: I will inspect the dashboard alert renderer and existing browser/WebSocket test harnesses, then add deterministic mixed-payload coverage for density, filtering, recovery/resync, navigation, responsiveness, and accessibility. I will run the relevant focused suites before committing and submitting.
---
author: oompah
created: 2026-08-03 23:47
---
Discovery: The prerequisites are committed on their task branches but not yet combined. dashboard.html currently has no browser harness; Chrome is available, so I will add deterministic headless-browser coverage that drives the real template and records semantic/layout outcomes. I will merge the three prerequisite branches locally to validate their composed contract, resolving only overlapping template changes.
---
author: oompah
created: 2026-08-03 23:53
---
Implementation: Added tests/test_dashboard_alert_experience.py, a deterministic headless-Chrome harness using an in-page WebSocket double. It covers production-shaped mixed alerts, desktop and phone layouts, bounded overflow, disclosure/focus semantics, task-card reachability, running-to-failed gate updates, sequence-gap full_sync, and clearing recovered audit transport warnings. The browser test exposed generic alerts being rendered three times (center, legacy banner, agent bar), so dashboard.html now uses the compact center as their one visible surface; legacy markup remains empty for compatibility. Updated the vertical-scroll regression contract accordingly.
---
author: oompah
created: 2026-08-03 23:55
---
Verification: focused regression command passed 149 tests: dashboard alert browser harness, alert center/safety/credential flows, intake lifecycle, audit/quality/repo-health panels, vertical layout, WebSocket full-sync, and fault injection. Chrome scenarios verified collapsed desktop height <=80px with a visible board, mobile internal list overflow, accessible details/focus order, running-to-failed gate updates, and a delivery-sequence gap converging to recovered state without reload.
---
author: oompah
created: 2026-08-04 00:07
---
Verification update: make test was attempted on e3f2f2750 but stopped before collection because the task-private venv is absent and sandboxed uv cannot create a DBus transient scope (kernel-thread rejection). Fallback full pytest collected 15,246 tests; it exposed only the known OOMPAH-675 order-dependent xdist timeout regressions. Those exact tests pass in isolation (3/3), as do the 149 directly affected tests. scripts/find_terminal_mutations.py oompah also passed (8 allowlisted mutations).
---
author: oompah
created: 2026-08-04 00:08
---
Completion: pushed 2361ecf83 (OOMPAH-745: Cover dashboard alert experience). Delivered deterministic headless-Chrome alert coverage plus the one-visible-surface contract, updated legacy regression expectations, and documented operator behavior. Final focused verification: 149 passed; terminal mutation scan passed; branch is clean and up to date with origin. The attempted Makefile gate is blocked only by the sandboxed uv transient-scope error, while the fallback broad-suite timeout flake is recorded above and passes in isolation.
---
author: oompah
created: 2026-08-04 00:08
---
Added browser-level alert density and recovery coverage
---
author: oompah
created: 2026-08-04 00:09
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 0, Tool calls: 94
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 26m 27s
- Log: OOMPAH-745__20260803T234321Z.jsonl
---
author: oompah
created: 2026-08-04 15:36
---
Integration found a rebase conflict on `epic-OOMPAH-740--task-OOMPAH-745`. Resolve it against `epic-OOMPAH-740`, run the required tests, push the same private branch, and `oompah task submit` it again.
---
<!-- COMMENTS:END -->
