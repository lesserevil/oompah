---
id: OOMPAH-287
type: task
status: In Progress
priority: 1
title: Add provenance metadata for external content entering Oompah
parent: OOMPAH-285
children: []
blocked_by:
- OOMPAH-286
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T14:51:40.852361Z'
updated_at: '2026-07-21T16:13:30.352147Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 20e9f264-29bb-4be7-8529-b166e4998697
oompah.task_costs:
  total_input_tokens: 18
  total_output_tokens: 4256
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 18
      output_tokens: 4256
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 18
    output_tokens: 4256
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:13:14.749081+00:00'
---
## Summary

Implement the provenance model from the threat-model task. Extend normalized issue, comment, and attachment representations so content records identify source, trust level, origin URL/actor where available, and whether content may be rendered to a model. Cover GitHub issue bodies/comments, PR metadata, webhook strings, CI/log excerpts, repository text, and attachments. Preserve backward compatibility for native tasks.

Dependency: Define the external-content trust model and prompt-injection threat model.

Tests: unit tests for every source, legacy native-task compatibility, serialization, and default-deny behavior for unknown sources.

Acceptance criteria: prompt code distinguishes trusted operator/task instructions from untrusted external text without parsing prose or source-specific fields.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 16:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:11
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 16:13
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed. OOMPAH-287 is the second child of OOMPAH-285 (the prompt-injection defense epic) and uniquely covers implementing provenance metadata in code. No existing task in the task store, plans, docs, or codebase addresses adding provenance/trust-level fields to normalized issue, comment, and attachment representations.

2. Evidence: Searched .oompah/tasks/ (all states), plans/, docs/, oompah/, and tests/ for 'provenance', 'trust level', 'trust_level', 'TrustLevel', 'ContentSource', 'external content', 'content record' — zero matches in any file. Reviewed OOMPAH-286 (Merged, the dependency) which delivered plans/prompt-injection-protection.md and 29 contract tests defining the trust model and provenance contract schema — but contains no implementation code for stamping provenance onto data objects. Reviewed OOMPAH-285 (In Progress epic) which lists OOMPAH-287 explicitly as a required child task. OOMPAH-288 through OOMPAH-291 are sibling tasks covering later stages (prompt rendering, triage hardening, server-side authority, regression suite) — none duplicate provenance metadata.

3. Remaining work/risks: Implement the provenance model from plans/prompt-injection-protection.md (§8 machine-readable provenance contract). Extend normalized issue/comment/attachment data classes with source, trust_level, origin_url, origin_actor, and model_renderable fields. Cover GitHub issue bodies/comments, PR metadata, webhook strings, CI/log excerpts, repository text, and attachments. Preserve backward compatibility for native tasks. Add unit tests for every source type, legacy native-task compatibility, serialization, and default-deny behavior for unknown sources. Risk: plans/prompt-injection-protection.md was merged on branch OOMPAH-286 but may not yet be on main or in this worktree — the implementation agent should pull or check the merged content before coding.

4. Recommended next focus: feature (implement provenance data model in Python — add ContentProvenance dataclass/TypedDict, patch intake bridge, GitHub comment/issue normalization, webhook handler, and prompt renderer to stamp provenance; then write unit tests).
---
author: oompah
created: 2026-07-21 16:13
---
Agent completed successfully in 99s (4274 tokens)
---
author: oompah
created: 2026-07-21 16:13
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 33, Tool calls: 25
- Tokens: 18 in / 4.3K out [4.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 39s
- Log: OOMPAH-287__20260721T161137Z.jsonl
---
author: oompah
created: 2026-07-21 16:13
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 16:13
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 16:13
---
Focus: Security Auditor
---
<!-- COMMENTS:END -->
