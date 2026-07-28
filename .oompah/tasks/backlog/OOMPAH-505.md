---
id: OOMPAH-505
type: feature
status: Backlog
priority: 1
title: Expose and configure explicit Claude and Codex model tiers
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:06:01.649921Z'
updated_at: '2026-07-28T15:06:54.053914Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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
<!-- COMMENTS:END -->
