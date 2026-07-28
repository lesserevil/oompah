---
id: OOMPAH-505
type: feature
status: In Progress
priority: 1
title: Expose and configure explicit Claude and Codex model tiers
parent: OOMPAH-502
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T15:06:01.649921Z'
updated_at: '2026-07-28T15:21:23.417086Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e76c1de6-5299-4ea3-92eb-c6d4e18f9093
oompah.work_branch: epic-OOMPAH-502
oompah.task_costs:
  total_input_tokens: 24
  total_output_tokens: 4765
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 24
      output_tokens: 4765
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 24
    output_tokens: 4765
    cost_usd: 0.0
    recorded_at: '2026-07-28T15:20:55.773130+00:00'
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
<!-- COMMENTS:END -->
