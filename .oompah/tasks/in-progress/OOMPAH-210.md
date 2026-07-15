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
updated_at: '2026-07-15T20:52:51.732672Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d6c34a6b-2970-4432-9f35-ad3f3b474c74
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
<!-- COMMENTS:END -->
