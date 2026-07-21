---
id: OOMPAH-288
type: task
status: In Progress
priority: 1
title: Render untrusted content in explicit prompt data boundaries
parent: OOMPAH-285
children: []
blocked_by:
- OOMPAH-287
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T14:51:41.895980Z'
updated_at: '2026-07-21T22:07:36.410864Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a62b41a4-5220-47e9-ac40-ad4073304ad4
---
## Summary

Update prompt rendering, continuation prompts, decomposition prompts, agent system prompt construction, and attachment rendering to consume provenance metadata. Delimit untrusted content in a stable escaped data block and add a non-bypassable instruction that content inside is reference data only and cannot override system, project, or task instructions. Prevent role markers, template syntax, control headers, and task-state directives from entering instruction-bearing positions. Preserve original content for human review.

Dependency: Add provenance metadata for external content entering Oompah.

Tests: adversarial issue/comment fixtures containing role changes, tool requests, instruction overrides, XML/Markdown delimiters, and Liquid-like syntax; assert rendering preserves text as data and emits the safety instruction exactly once.

Acceptance criteria: no external content is interpolated into an instruction-bearing prompt position.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 21:51
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 21:51
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 22:07
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed. OOMPAH-288 is the third child of OOMPAH-285 (Defend Oompah agents against prompt injection) and describes a unique implementation task not covered by any other existing task in the tracker.

2. Evidence reviewed:
   - Searched .oompah/tasks/ (all states: archived, merged, done, backlog, needs-ci-fix, needs-rebase, in-progress) for keywords: untrusted, prompt injection, data boundary, provenance, prompt rendering, sanitize, render+untrusted, role marker, bypassable, reference data. Zero hits except OOMPAH-287 and OOMPAH-286 (both dependencies, not duplicates).
   - OOMPAH-285 (epic, In Progress): parent epic; explicitly lists OOMPAH-288 as a required child with its own scope (prompt data boundaries, safety instruction).
   - OOMPAH-286 (Merged): Defines the threat model in plans/prompt-injection-protection.md — a planning artifact, not an implementation of rendering.
   - OOMPAH-287 (Merged): Adds provenance dataclass/enums and initial XML wrapping in prompt.py, focus.py, github_intake_bridge.py — this is the dependency for OOMPAH-288, NOT a duplicate. OOMPAH-287 implements the data model; OOMPAH-288 extends rendering to ALL prompt positions, adds the non-bypassable safety instruction, prevents role markers/template syntax from entering instruction-bearing positions, and adds adversarial tests.
   - OOMPAH-289, 290, 291 (Open siblings): Cover focus triage hardening, server-side authority, and regression suite respectively — each distinct in scope.
   - No archived or merged task covers the OOMPAH-288 scope.

3. Remaining work/risks: Implement (building on OOMPAH-287's provenance.py and XML wrapper foundation): (a) extend safe rendering to continuation prompts, decomposition prompts, agent system prompt construction, and attachment rendering; (b) add non-bypassable safety instruction text to every untrusted data block; (c) add content escaping to prevent role markers, template syntax, control headers, and task-state directives from entering instruction-bearing positions; (d) write adversarial test fixtures (role changes, tool requests, instruction overrides, XML/Markdown delimiters, Liquid-like syntax); assert safety instruction is emitted exactly once and external content stays in data position. Risks: OOMPAH-287's wrapping may already cover some of these paths — implementer should audit what was already wrapped to avoid redundancy.

4. Recommended next focus: feature (security implementation — extend provenance-aware rendering to all prompt positions and add adversarial tests as specified in the description).
---
<!-- COMMENTS:END -->
