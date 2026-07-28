---
id: OOMPAH-505
type: feature
status: Open
priority: 1
title: Expose and configure explicit Claude and Codex model tiers
parent: OOMPAH-502
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
- focus-complete:frontend
- needs:devops
assignee: null
created_at: '2026-07-28T15:06:01.649921Z'
updated_at: '2026-07-28T15:41:34.497738Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e76c1de6-5299-4ea3-92eb-c6d4e18f9093
oompah.work_branch: epic-OOMPAH-502
oompah.task_costs:
  total_input_tokens: 9628065
  total_output_tokens: 30913
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 9628065
      output_tokens: 30913
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 24
    output_tokens: 4765
    cost_usd: 0.0
    recorded_at: '2026-07-28T15:20:55.773130+00:00'
  - profile: standard
    model: unknown
    input_tokens: 9628041
    output_tokens: 26148
    cost_usd: 0.0
    recorded_at: '2026-07-28T15:41:30.391589+00:00'
---
## Summary

Finding: both ACP backends already forward explicit models. ClaudeAgentOptions accepts installed CLI aliases fable, sonnet, and opus; Codex accepts explicit Responses model IDs. The dashboard incorrectly equates lack of model-catalog discovery with lack of manual model selection, and current fast/standard/deep roles all round-robin over the same provider defaults.

Implementation: separate has_catalog from supports_manual_model_selection in ACP backend descriptors/API/UI. Permit operator-entered model IDs for ACP providers without catalogs while retaining backend validation and safe fallback. Add dispatch tests proving role candidates propagate the exact explicit model through Claude and Codex subscription sessions and telemetry. Document manual ACP model entry. After deployment, configure role candidates as: fast = Claude/fable plus Codex/gpt-5.6-luna; standard = Claude/sonnet plus Codex/gpt-5.6-terra; deep = Claude/opus plus Codex/gpt-5.6-sol. Preserve round-robin, credentials, provider health, and project whitelist behavior.

Tests: backend descriptor/API/UI tests; RoleStore validation with empty ACP catalogs; orchestrator and backend handoff tests for all six mappings; unknown/invalid configured model failure behavior; configuration round-trip and running-state telemetry. Use official current model identifiers and do not hardcode local provider IDs in production defaults.

Acceptance criteria: the UI truthfully supports manual model selection; each tier resolves to a distinct model within each provider; live roles contain the six explicit mappings; running tasks report the selected provider/model; existing default-model behavior remains backward compatible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:06
---
Claimed for manual implementation by the current Codex session. Held in Backlog while the shared epic branch is built so Oompah does not dispatch another agent; status will move to In Progress and Done as this session completes the slice.
---
author: oompah
created: 2026-07-28 15:18
---
Confirmed the remaining functional gap: backend sessions already forward explicit models, but the Claude alias allowlist omits fable and the role matrix renders only an empty SDK-managed selector when an ACP catalog is absent. I am adding a first-class backend manual-selection capability, a free-text role control for those backends, accurate API notes, and six-tier propagation tests while retaining empty-model SDK fallback.
---
author: oompah
created: 2026-07-28 15:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 15:19
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 15:20
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate confirmed. OOMPAH-505 is a unique, first-of-its-kind task.

**Search performed:**
- Scanned all .oompah/tasks/ states (open, backlog, merged, archived — 272+ task files)
- grep patterns: model tier, model selection, fable, has_catalog, ClaudeAgent, CodexAgent, role candidate, RoleStore, gpt-5.6, fast/standard/deep, ACP backend
- Checked sibling tasks of the parent epic OOMPAH-502 (503, 504, 506, 507, 508, 509, 510)
- Searched plans/ and docs/ for any existing design docs on this feature

**Closest candidates reviewed and ruled out:**
- OOMPAH-503 (Done): limits automatic duplicate detection scope — unrelated
- OOMPAH-504 (Done): compact agent prompt history — unrelated
- OOMPAH-211 (Archived): deliver task comments to running agents — unrelated
- No task in any state covers: has_catalog vs supports_manual_model_selection, ACP backend model tier configuration, Claude fable/sonnet/opus alias allowlist, Codex gpt-5.6-luna/terra/sol role mapping, or RoleStore validation with empty catalogs

**Evidence:** All task titles and grep results searched show nothing overlapping with model tier dispatch or ACP backend manual model selection.

**Remaining work:**
1. Add supports_manual_model_selection field to ACP backend descriptors (separate from has_catalog)
2. Expand Claude alias allowlist to include fable
3. Add free-text model input to role UI for ACP backends without catalogs
4. Configure role candidates: fast=Claude/fable+Codex/gpt-5.6-luna, standard=Claude/sonnet+Codex/gpt-5.6-terra, deep=Claude/opus+Codex/gpt-5.6-sol
5. Write dispatch tests for all six tier mappings propagating through ACP sessions and telemetry
6. Document manual ACP model entry
7. Ensure backward-compatible fallback when no model is configured

**Recommended next focus:** feature
---
author: oompah
created: 2026-07-28 15:20
---
Agent completed successfully in 108s (4789 tokens)
---
author: oompah
created: 2026-07-28 15:20
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 43, Tool calls: 35
- Tokens: 24 in / 4.8K out [4.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 48s
- Log: OOMPAH-505__20260728T151912Z.jsonl
---
author: oompah
created: 2026-07-28 15:21
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 15:21
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 15:21
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-28 15:21
---
Understanding: I am implementing the frontend slice by tracing ACP backend capability metadata into the role configuration UI, separating catalog discovery from manual model entry, adding an accessible framework-consistent control for catalog-less backends, and covering behavior with existing UI/API tests. I will verify whether backend/configuration work remains and hand off with evidence if needed.
---
author: oompah
created: 2026-07-28 15:22
---
Code and documentation are implemented and pushed in commit 23d1c043b. ACP descriptors now separate catalog discovery from manual model selection; the role matrix accepts manual IDs for empty-catalog Claude/Codex providers; fable is forwarded; all six requested tier mappings reach the ACP session unchanged. Focused provider/role/backend suite: 402 passed. Keeping this task In Progress until the six live role candidates are applied after deployment.
---
author: oompah
created: 2026-07-28 15:22
---
Discovery: The role API and RoleStore already accept arbitrary explicit models for ACP providers whose catalog is empty, but providers.html renders only a one-option SDK-managed select and status. GET /api/v1/acp-backends currently defines supports_model_selection as identical to has_catalog, so the UI cannot distinguish manual selection from catalog discovery. Relevant code: oompah/templates/providers.html renderRoleMatrix/loadAcpBackends and oompah/server.py acp_backend_descriptors.
---
author: oompah
created: 2026-07-28 15:25
---
Implementation: Added a first-class supports_manual_model_selection capability to ACP backends/descriptors (Claude and Codex true, independent of has_catalog), preserved the legacy catalog signal, and exposed it in fetch-model responses. The role matrix now renders an accessible free-text model control for catalog-less/manual-capable ACP providers, preserves blank SDK-default behavior, reports manual/default status accurately, and rerenders when async descriptors arrive. Added backend/API/UI regression tests.
---
author: oompah
created: 2026-07-28 15:34
---
Verification: Focused provider/backend/role-matrix tests pass (241). Full pytest fallback completed with 12,638 passed, 7 skipped and one sandbox-only failure writing ~/.oompah/agent-logs; that exact test passes when OOMPAH_AGENT_LOG_DIR points to writable /tmp. JavaScript syntax check and make check-secrets also pass. make test itself could not start because the environment's Snap-packaged uv fails DBus transient-scope creation.
---
author: oompah
created: 2026-07-28 15:39
---
Focus handoff: frontend

Outcome: Completed and pushed the frontend/API presentation slice. The role matrix now shows an accessible free-text model input for manual-capable catalog-less ACP backends, preserves blank SDK-default fallback, distinguishes manual vs SDK-default status, and rerenders when async backend descriptors arrive. This is commit 020199d32 on epic-OOMPAH-502, rebased on the existing feature implementation 23d1c043b.

Relevant files/evidence: oompah/templates/providers.html and tests/test_providers_ui.py contain the material increment; the rebase retained upstream descriptor, fable, dispatch, telemetry, and documentation work. Focused provider/backend/role matrix suite: 241 passed. Full suite fallback: 12,638 passed, 7 skipped, with one sandbox-only ~/.oompah/agent-logs write failure that passes under a writable OOMPAH_AGENT_LOG_DIR. JavaScript syntax and make check-secrets pass.

Remaining work/risk: Deploy/restart the updated service, apply the six live round-robin role candidates (fast Claude/fable + Codex/gpt-5.6-luna; standard Claude/sonnet + Codex/gpt-5.6-terra; deep Claude/opus + Codex/gpt-5.6-sol), verify provider IDs/credentials/project whitelist and running telemetry, then close the task. Do not hardcode local provider IDs in production defaults.

Recommended next focus: devops.
---
author: oompah
created: 2026-07-28 15:41
---
Agent completed successfully in 1225s (9654189 tokens)
---
author: oompah
created: 2026-07-28 15:41
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 100
- Tokens: 9.6M in / 26.1K out [9.7M total]
- Cost: $0.0000
- Exit: normal, Duration: 20m 25s
- Log: OOMPAH-505__20260728T152107Z.jsonl
---
author: oompah
created: 2026-07-28 15:41
---
Focus handoff from `frontend` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
<!-- COMMENTS:END -->
