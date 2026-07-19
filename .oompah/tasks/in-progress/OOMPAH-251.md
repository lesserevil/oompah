---
id: OOMPAH-251
type: task
status: In Progress
priority: null
title: Make Release Delivery candidate discovery bounded for Trickle-scale history
parent: null
children: []
blocked_by:
- OOMPAH-250
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-19T22:01:10.371010Z'
updated_at: '2026-07-19T22:09:29.195899Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 4ba1a6b4-9b3f-44a1-b20e-e359ad138411
oompah.task_costs:
  total_input_tokens: 89662
  total_output_tokens: 5509
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 89662
      output_tokens: 5509
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 89647
    output_tokens: 593
    cost_usd: 0.0
    recorded_at: '2026-07-19T22:07:15.972029+00:00'
  - profile: standard
    model: unknown
    input_tokens: 15
    output_tokens: 4916
    cost_usd: 0.0
    recorded_at: '2026-07-19T22:09:26.231670+00:00'
---
## Summary

Problem

After OOMPAH-250 correctly injects Trickle's project tracker, the live GET Release Delivery backlog for Trickle release/0.11 no longer completes within the UI/request timeout. Candidate discovery iterates all Merged records on the request path and can perform sequential work-branch rev-list calls, SCM PR commit API calls, per-item title reads, and tracker-only classification. With thousands of main commits and dozens of merged records this blocks the page instead of returning candidate rows.

Required implementation

- Make construction of the primary task/epic candidate list bounded and cacheable. It must not perform unbounded sequential SCM or subprocess operations per historical Merged item during a request.
- Establish a clear performance budget for the backlog endpoint and enforce per-operation timeouts; use a bounded concurrency/batch strategy or a durable per-project candidate index/cache.
- Build and return primary rows before optional diagnostics, title enrichment, and tracker-only classification. Those nonessential fields may be cached, deferred, or bounded, but must never block the primary list.
- Preserve correctness: candidate eligibility still requires Merged task/epic evidence and source commits reachable from default branch; release ancestry/ledger still control delivery status.
- Emit structured timing/logging sufficient to identify which discovery phase exceeds budget.

Tests

- Performance/API regression using a synthetic Trickle-scale fixture (thousands of source commits and dozens of Merged items, including deleted work branches and PR references) verifies the primary needs-delivery response completes within the documented service/UI timeout.
- Assert external SCM lookups and git subprocess calls are bounded rather than proportional to all historical items.
- Verify primary candidate rows are returned even when optional title/diagnostic enrichment is slow or fails.
- Regression test retains correct Not selected and delivered filtering for the returned rows.

Acceptance criteria

- The live Trickle release/0.11 Release Delivery dialog renders a non-empty, selectable candidate list without timing out.
- Optional unassociated-commit diagnostics cannot delay the primary backlog.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 22:02
---
Requirement update from project owner: a long Trickle-scale discovery run is acceptable, provided the Release Delivery UI gives meaningful progress. This supersedes any implication that all discovery must complete synchronously within a short HTTP/UI timeout. Implement an observable asynchronous refresh model: (1) start or reuse one refresh job per project plus selected release branch, (2) retain and display the last completed candidate list while a refresh is active, (3) expose progress through the existing dashboard transport or a dedicated status endpoint with phase, completed/total counts where knowable, elapsed time, and actionable failure state, (4) render this status in the Release Delivery dialog with a determinate progress bar when a total is known and explicit phase text otherwise, and (5) allow retry after failure. Suggested phases: loading merged task metadata; resolving source commits/PR evidence; comparing release-branch ancestry; preparing rows; optional diagnostics. The primary list must not disappear or show an unexplained blank state while checks are running. Add dashboard and API tests for start, in-progress updates, successful completion, retained stale result, failure, and retry.
---
author: oompah
created: 2026-07-19 22:06
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-19 22:06
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 22:07
---
Agent completed successfully in 24s (90240 tokens)
---
author: oompah
created: 2026-07-19 22:07
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 89.6K in / 593 out [90.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 24s
- Log: OOMPAH-251__20260719T220656Z.jsonl
---
author: oompah
created: 2026-07-19 22:07
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-251`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-19 22:07
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-19 22:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 22:09
---
Focus handoff: duplicate_detector

1. Outcome: OOMPAH-251 is NOT a duplicate. Duplicate screening complete.

Candidates reviewed:
- OOMPAH-237 (Merged, epic): "Fix Release Delivery backlog candidate discovery and timeout" — the parent epic that covered the original candidate-discovery and timeout bugs. Already merged. OOMPAH-251 is a distinct, follow-on issue arising AFTER OOMPAH-250 was deployed.
- OOMPAH-238 (Merged, child of OOMPAH-237): Fixed candidate discovery algorithm to derive from tracker Merged records. Different scope — was about algorithm correctness, not performance at Trickle scale with many Merged records.
- OOMPAH-239 (Merged, child of OOMPAH-237): Bounded unassociated-commit diagnostic git calls (per-commit diff-tree subprocess cap). Different scope — was about the unassociated-commit diagnostics section, not the primary candidate list construction.
- OOMPAH-240, OOMPAH-241 (Merged, children of OOMPAH-237): Dashboard and Trickle regression tests. Distinct scopes.
- OOMPAH-250 (Merged): Injected the correct project-scoped tracker for Release Delivery. Its own comment explicitly filed OOMPAH-251 after post-deploy validation showed the next bottleneck.
- OOMPAH-252 (Open): Depends on OOMPAH-251; it moves Release Delivery to a dedicated page. Different scope.
- No other merged/archived task covers: async refresh model, per-project candidate index/cache, progress phase reporting, or the specific bottleneck of sequential SCM/rev-list calls when iterating many Trickle Merged records.

2. Key evidence:
- OOMPAH-250 comment (post-deploy): 'the live Trickle release/0.11 backlog request now exceeds the UI timeout instead of returning rows. Candidate discovery is unbounded on the request path across historical Merged records and optional enrichment. Filed OOMPAH-251 for bounded/cached primary candidate discovery with a Trickle-scale API regression.'
- OOMPAH-251's requirement update: 'implement an observable asynchronous refresh model' with per-project refresh jobs, stale result retention, progress phases, and UI progress bar. This is architecturally distinct from the per-commit subprocess cap in OOMPAH-239.

3. Relevant files (from prior work context):
- oompah/release_delivery_backlog.py — ItemBacklogService.get_backlog() — primary candidate list construction, sequential per-item SCM/subprocess calls
- oompah/server.py — api_release_delivery_backlog route
- oompah/release_delivery_inventory.py — SCM/subprocess helpers used during discovery
- tests/test_server_release_delivery_backlog.py — API regression tests
- tests/test_release_delivery_backlog.py — unit tests

4. Remaining work: Full implementation of async refresh model for Release Delivery candidate discovery, with progress visibility in the UI.

Recommended next focus: feature (backend async refresh model + API endpoints) followed by frontend (progress UI in Release Delivery dialog).
---
author: oompah
created: 2026-07-19 22:09
---
Agent completed successfully in 105s (4931 tokens)
---
<!-- COMMENTS:END -->
