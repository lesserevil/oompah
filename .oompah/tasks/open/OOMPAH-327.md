---
id: OOMPAH-327
type: task
status: Open
priority: 2
title: Expose GitLab configuration and health in UI, API, and ACP tools
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-319
- OOMPAH-323
- OOMPAH-325
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T20:34:41.130372Z'
updated_at: '2026-07-22T05:53:36.639619Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d0dde072-370e-43d5-b34b-7bad5bd69fc5
oompah.task_costs:
  total_input_tokens: 28
  total_output_tokens: 7130
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 28
      output_tokens: 7130
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 28
    output_tokens: 7130
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:53:32.882502+00:00'
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, Webhooks, UI, bootstrap, and operations.

Extend project create/update/detail REST APIs, Projects UI, task CLI-compatible project payloads, and ACP project tools for forge_kind, forge_base_url, GitLab tracker/intake settings, masked project token, public webhook endpoint, hook health, and pipeline capability warnings. Keep old GitHub fields accepted and rendered correctly. Use “Merge Request” wording only when the project forge is GitLab.

Tests:
- API request/response compatibility for legacy GitHub payloads and GitLab payloads.
- UI DOM/JavaScript contract tests for conditional controls, token masking, validation errors, and hook-health display.
- ACP schema/list/create/update contract tests.

Acceptance criteria:
- Operators can configure and diagnose a GitLab project entirely through Oompah interfaces.
- GitHub project UI/API behavior is unchanged.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:47
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:52
---
Understanding: As Duplicate Investigator, I am screening OOMPAH-327 ('Expose GitLab configuration and health in UI, API, and ACP tools') before any implementation begins. The task is a child of the OOMPAH-318 GitLab forge parity epic. My plan: search all task records, plans, docs, and git history for any existing task that covers the same UI/API/ACP scope for GitLab config (forge selector, forge_base_url field, GitLab tracker/intake controls, masked project token, webhook endpoint/health display, pipeline warnings, 'Merge Request' terminology, and ACP tool schema extensions).
---
author: oompah
created: 2026-07-22 05:53
---
Focus handoff: duplicate_detector\n\n1. **Outcome:** No duplicate confirmed. OOMPAH-327 is a distinct, unique child of OOMPAH-318 with a scope that no existing task (in any state) covers.\n\n2. **Evidence searched:**\n   - All .oompah/tasks/ states (archived, backlog, done, in-progress, merged, open) — no file for OOMPAH-319 through OOMPAH-329/OOMPAH-353 exists under main; those live on epic-OOMPAH-318 branch. Retrieved them via `oompah task view`.\n   - Searched plans/, docs/, README.md for gitlab/forge_kind/ACP/webhook-health/token-mask/forge-selector — no task found covering UI/API/ACP exposure.\n   - Reviewed all OOMPAH-318 sibling children in full:\n     - OOMPAH-319 (Done): forge model/persistence; **explicitly excludes UI controls**.\n     - OOMPAH-320 (Done): forge-neutral SCM/CI provider contract; no UI scope.\n     - OOMPAH-321 (Done): GitLab MR provider parity; no UI scope.\n     - OOMPAH-322 (Done): GitLab pipeline CI status; no UI scope.\n     - OOMPAH-323 (Done): GitLab Issues tracker + governance; no UI scope.\n     - OOMPAH-325 (Done): GitLab project-hook lifecycle and webhook event parity; covers hook CREATION/health BACKEND, not the UI/API exposure of hook health.\n     - OOMPAH-326 (Done): review, YOLO, release delivery integration; no UI scope.\n     - OOMPAH-324 (Open): external issue intake generalization; different scope.\n     - OOMPAH-328 (Open): bootstrap and operator docs; different scope.\n     - OOMPAH-329 (Open): cross-forge acceptance tests; different scope.\n   - Git log: all commits for OOMPAH-319 through OOMPAH-326 are code/test backend; no UI/ACP/REST extension commits found.\n\n3. **Remaining work and risks:**\n   - Extend REST API (create/update/detail endpoints) to expose forge_kind, forge_base_url, GitLab tracker/intake settings, masked project token, public webhook endpoint URL, hook health, and pipeline capability warnings.\n   - Extend Projects UI with forge selector, GitLab base URL field, GitLab tracker/intake controls, token masking, webhook endpoint/health display, and 'Merge Request' terminology conditional on forge_kind == gitlab.\n   - Extend ACP project tools schema/list/create/update contracts.\n   - Tests: API compatibility (legacy GitHub payloads + GitLab payloads), UI DOM/JavaScript contract tests (conditional controls, token masking, validation errors, hook-health display), ACP schema/list/create/update contract tests.\n   - Risk: OOMPAH-325 (hook health backend) must be confirmed fully landed before UI can surface health data.\n\n4. **Recommended next focus:** feature (backend REST API + ACP tools) with a follow-on needs:frontend for the Projects UI work. If the same agent can handle both backend and frontend, go directly to feature.
---
author: oompah
created: 2026-07-22 05:53
---
Agent completed successfully in 389s (7158 tokens)
---
author: oompah
created: 2026-07-22 05:53
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 56, Tool calls: 39
- Tokens: 28 in / 7.1K out [7.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 29s
- Log: OOMPAH-327__20260722T054706Z.jsonl
---
author: oompah
created: 2026-07-22 05:53
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
<!-- COMMENTS:END -->
