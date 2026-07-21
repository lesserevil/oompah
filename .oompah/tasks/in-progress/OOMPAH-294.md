---
id: OOMPAH-294
type: task
status: In Progress
priority: 1
title: Define repository-map artifact and state-branch lifecycle
parent: OOMPAH-293
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T15:13:47.496504Z'
updated_at: '2026-07-21T15:45:24.790682Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 2898ad89-dacf-4db5-8e71-22cf17fe3fc7
---
## Summary

Write the implementation design and add the core model/types for a repository-map artifact. Define a versioned, deterministic JSON schema containing: repository identity, analyzed commit SHA, generator version, indexed files, symbol tags, relationship edges, generation timestamp, and rendering metadata. Define the exact state-branch path, atomic-write procedure, freshness rule (map SHA must equal checkout SHA), retention/pruning policy, and behavior for unavailable or unsupported repositories.\n\nDo not add parsing or prompt injection in this task. The artifact must be data only; it must never be executed or interpreted as instructions.\n\nTests:\n- Unit-test schema serialization/deserialization and schema-version rejection.\n- Unit-test deterministic output for identical input and invalidation when the commit SHA changes.\n- Unit-test all path construction and state-branch writes remain within the project state namespace.\n\nAcceptance criteria:\n- A documented schema and lifecycle exist in plans/.\n- Code exposes a typed artifact contract for later tasks.\n- Artifacts are keyed by repository identity and commit SHA and are safe to read only when fresh.\n- Tests pass through the project Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 15:45
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 15:45
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
