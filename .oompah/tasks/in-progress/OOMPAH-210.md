---
id: OOMPAH-210
type: bug
status: In Progress
priority: 2
title: Detect and surface unavailable GitHub check-run access
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-15T20:39:59.115969Z'
updated_at: '2026-07-15T21:02:39.205997Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a4d29742-46c6-4d2d-879c-84d6c64211ec
oompah.task_costs:
  total_input_tokens: 153
  total_output_tokens: 3870
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 153
      output_tokens: 3870
      cost_usd: 0.0
  runs:
  - profile: deep
    model: unknown
    input_tokens: 153
    output_tokens: 3870
    cost_usd: 0.0
    recorded_at: '2026-07-15T20:52:36.542225+00:00'
---
## Summary

Triggered by: TRICKLE-26

Oompah received HTTP 403 from GET /repos/NVIDIA-Omniverse/trickle/commits/<sha>/check-runs while reconciling PR #277. It consequently could not observe the failed CI lint check or automatically create/dispatch a CI-fix task. Make check-run access failures visible as a project capability/degraded-state error, document the exact required token permission and alternatives, and ensure CI repair dispatch has a reliable fallback when check-runs cannot be read. Add regression tests for 403 handling and failed-check detection.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-15 20:41
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-15 20:41
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-15 20:41
---
Understanding: This issue requires implementing 403 error handling for GitHub check-runs API. Plan: (1) Find where check-runs are fetched in oompah, (2) Add 403 detection + degraded-state surfacing, (3) Document required token permission, (4) Add fallback for CI repair dispatch when check-runs unavailable, (5) Write regression tests. Starting codebase exploration now.
---
author: oompah
created: 2026-07-15 20:45
---
Discovery: Root cause found in oompah/scm.py GitHubProvider._fetch_ci_status_and_warnings() (line ~841). When GET /repos/{repo}/commits/{sha}/check-runs returns HTTP 403, the code silently falls through the 'if cr.status_code == 200:' check with NO warning logged. Three failure modes: (1) GitHub Actions-only repo + 403 → returns '' (unknown status, CI failures invisible); (2) legacy-pending + 403 → incorrectly returns '' instead of 'pending'; (3) legacy-failure + 403 → returns 'failed' (works, but no warning surfaced). The ci_warnings list (already used for 'unavailable_runner' warnings and surfaced in the UI) is the right place to expose a 'check_runs_forbidden' warning. Required token permission: fine-grained PAT needs 'Checks: Read'; classic tokens need 'repo' scope. Fix: (a) log WARNING once-per-repo per instance, (b) add check_runs_forbidden warning to ci_warnings, (c) fix legacy-pending+403 to return 'pending', (d) add regression tests.
---
author: oompah
created: 2026-07-15 20:52
---
Operator clarification: GitHub's fine-grained PAT editor does not offer a Checks permission, so do not make Checks: Read a prerequisite or ask operators to grant it. Replace/augment check-runs polling with the GitHub Actions workflow-runs/jobs APIs using the available Actions: Read repository permission. The implementation must detect failed workflow jobs and dispatch CI repair from that data, retain a clear degraded-capability warning if neither source is available, and update PAT docs to list Actions: Read for CI observation.
---
author: oompah
created: 2026-07-15 20:52
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 95
- Tokens: 153 in / 3.9K out [4.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 11m 35s
- Log: OOMPAH-210__20260715T204107Z.jsonl
---
author: oompah
created: 2026-07-15 20:52
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-15 20:52
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-15 20:53
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-15 20:53
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-15 20:53
---
Understanding: Previous agents identified the root cause in oompah/scm.py GitHubProvider._fetch_ci_status_and_warnings(). When GET /repos/{repo}/commits/{sha}/check-runs returns HTTP 403, the code silently falls through with no warning logged. The operator clarification says GitHub fine-grained PATs don't offer a Checks permission, so we should replace/augment check-runs polling with the GitHub Actions workflow-runs/jobs APIs using Actions: Read permission. Plan: (1) Read the current scm.py code around check-runs fetching, (2) Add workflow-runs/jobs API as primary/fallback source, (3) Add degraded-capability warning when neither source works, (4) Update PAT docs, (5) Write regression tests.
---
author: oompah
created: 2026-07-15 21:01
---
Implementation complete. Changes in oompah/scm.py:

1. Added _fetch_workflow_runs_ci_status() method: queries GET /repos/{repo}/actions/runs?head_sha={sha} (requires Actions: Read only). Returns ('', []) when API is accessible but no runs found (vs. None when API is unavailable/403), allowing callers to distinguish 'empty data' from 'API forbidden'.

2. Modified _fetch_ci_status_and_warnings() to handle 403 from check-runs:
   - On 403: logs a WARNING, then calls _fetch_workflow_runs_ci_status() as fallback
   - If workflow-runs succeeds: uses its status (respecting legacy_pending/legacy_failure logic)
   - If workflow-runs also fails (403/error): adds a check_runs_forbidden capability warning to ci_warnings so the UI can surface a degraded-state notice
   - Fixes the previously-silent failure: before this change, a 403 from check-runs would silently return '' (making CI failures invisible)

3. Docs updated: docs/managed-project-onboarding.md and docs/operator-runbook.md now document Actions: Read as required for CI observation with fine-grained PATs.

17 new regression tests added in tests/test_scm.py::TestFetchCiStatusCheckRunsForbidden covering: 403 fallback to workflow-runs (failed/passed/pending/empty/timed_out), legacy_pending+403, legacy_failure+403, both-APIs-forbidden degraded warning, and unit tests for _fetch_workflow_runs_ci_status.
---
author: oompah
created: 2026-07-15 21:02
---
Verification: All 166 tests in tests/test_scm.py pass (149 pre-existing + 17 new regression tests). The 3 failures in test_dashboard_release_delivery_ui.py::TestSelection are pre-existing and unrelated to this change (confirmed by running them before applying my changes). Full test suite: 8912 passed, 3 pre-existing failures, 28 skipped.
---
<!-- COMMENTS:END -->
