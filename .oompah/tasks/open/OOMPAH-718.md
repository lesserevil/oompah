---
id: OOMPAH-718
type: task
status: Open
priority: null
title: Detect and repair container-level cycles from cross-epic finish dependencies
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T13:10:18.934341Z'
updated_at: '2026-08-03T13:10:21.506526Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction: the Exocomp Mission Control roadmap has 38 Ready to Integrate child tasks at attempts=0 and no active integration. EXOCOMP-142 in epic EXOCOMP-129 depends on EXOCOMP-171 in sibling epic EXOCOMP-134. EXOCOMP-171 depends on completed EXOCOMP-141, whose integrated SHA is reachable only from the still-incomplete epic EXOCOMP-129. The raw task dependency graph is acyclic, but the required-code/container graph is cyclic: epic 129 cannot progress until task 171 lands, while epic 134 cannot make task 141 code reachable through its authorized parent-only synchronization path. OOMPAH-562 and OOMPAH-633 repair stale parent ancestry but intentionally forbid unrelated sibling synchronization, so this case remains permanently Ready with attempts=0 and no alert.

Implementation scope:
- Build a container-level dependency/reachability graph for shared nested epics. Detect cycles where a task in one nonterminal epic depends on a completed task whose code is confined to another nonterminal sibling epic, including longer cycles across several epics.
- Validate new dependency/decomposition mutations against this graph and reject or explain graphs that have no authorized delivery order.
- For existing graphs, choose a deterministic safe repair: propagate the exact prerequisite commit through the common authoritative ancestor/dependent container under compare-and-swap fencing, or route to an explicit actionable repair state. Never silently merge arbitrary sibling work.
- Preserve exact dependency commit ancestry, normal finish ordering, private task heads, shared epic ownership, quality gates, and terminal audits.
- Ensure one blocked group does not suppress independent integration groups and expose an alert with the cycle path, affected Ready rows, and selected repair.

Relevant code: dependency mutation and epic decomposition validation, orchestrator integration dependency/reachability analysis, nested epic synchronization policy, integration queue health/state summaries, and dashboard diagnostics.

Required tests:
- Reproduce EXOCOMP-142 -> EXOCOMP-171 -> completed EXOCOMP-141 confined to EXOCOMP-142 parent epic and detect the container cycle before indefinite attempts=0.
- Cover a longer multi-epic cycle and a valid cross-epic dependency whose parent has already landed.
- Prove the selected repair preserves the exact prerequisite SHA and lets both epic queues advance in dependency order.
- Prove unrelated sibling code is never imported and compare-and-swap races retry safely.
- Prove restart/idempotency, actionable alerting, and independent project progress.

Acceptance criteria:
- No Ready queue can remain indefinitely at attempts=0 solely because its dependency graph is acyclic at task level but cyclic at container reachability level.
- The live Exocomp dependency cycle is detected with an authorized repair path.
- Focused dependency, parallel-epic, integration-queue, server-state, and full make test gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

