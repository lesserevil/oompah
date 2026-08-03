---
id: OOMPAH-718
type: task
status: In Progress
priority: 0
title: Detect and repair container-level cycles from cross-epic finish dependencies
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- merge-conflict
assignee: null
created_at: '2026-08-03T13:10:18.934341Z'
updated_at: '2026-08-03T14:10:39.317543Z'
work_branch: OOMPAH-718
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/678
review_number: '678'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2fe699f516cdf2f6b36f5640c87410f715e321759bec79c16b66e7f1ef3d2fb9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T13:11:17.260452+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Duplicate preflight verdict: no_duplicate\nMatches: none\n\
    I need to carefully investigate whether OOMPAH-718 is a duplicate of any existing\
    \ active task. Let me analyze the current task and review the task corpus.\n\n\
    ## Understanding OOMPAH-718\n\n**Title**: Detect and repair container-level cycles\
    \ from cross-epic finish dependencies\n\n**Core Problem**: \n- A task in one nonterminal\
    \ epic depends on a completed task whose code is confined to another nonterminal\
    \ sibling epic\n- The raw task dependency graph is acyclic, but the **container/reachability\
    \ graph is cyclic**\n- This causes 38 Ready to Integrate child tasks to remain\
    \ indefinitely at attempts=0 with no alert\n- Example: EXOCOMP-142 \u2192 EXOCOMP-171\
    \ \u2192 EXOCOMP-141 (confined to parent EXOCOMP-129)\n\n**Scope**:\n- Build container-level\
    \ dependency/reachability graphs\n- Detect cycles across nested/sibling epics\n\
    - Validate new mutations against this graph\n- Choose deterministic safe repairs\n\
    - Expose actionable alerts\n\n## Searching the Task Corpus for Related Active\
    \ Tasks\n\nLet me review each task in the corpus for active (non-terminal) duplicates:\n\
    \n**Archived Task Analysis** (excluding these as per instructions):\n- OOMPAH-162:\
    \ \"Tolerate stacked children merged to default branch\" (Archived) - about handling\
    \ different PR merge targets, not container cycles\n- OOMPAH-163: \"Allow generated\
    \ epic target branches through dispatch\" (Archived) - about branch validation\
    \ rules, not dependency cycles\n- OOMPAH-165: \"Fix shared epic landed detection\
    \ before main merge\" (Archived) - about verifying when epic branch lands, not\
    \ about cross-epic reachability\n- OOMPAH-166-175: All about epic strategy standardization,\
    \ configuration, and release addendums (Archived) - not about cycle detection\n\
    \n**Scanning across full corpus**:\n- No active task addresses container-level\
    \ (epic-level) cycle detection\n- No active task addresses cross-epic dependency\
    \ reachability analysis\n- No active task deals with distinguishing acyclic task\
    \ graphs from cyclic container graphs\n- Previous related work (OOMPAH-162, OOMPAH-165)\
    \ focus"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 52f3feee-43e0-4d49-9655-966b5498dc21
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1671
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1671
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1671
    cost_usd: 0.0
    recorded_at: '2026-08-03T13:11:17.258287+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-718__20260803T131051Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-718
    source_sha: b97187abdd50d76deda75be427f26049fd396cb6
    completed_at: '2026-08-03T13:11:17.285636+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-718
  head_sha: c9734b0cf5e7ce375b31350ee9543627b5facc0a
  submitted_at: '2026-08-03T13:44:08.534408+00:00'
  updated_at: '2026-08-03T13:44:08.534408+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/678
oompah.review_number: '678'
oompah.work_branch: OOMPAH-718
oompah.target_branch: main
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 13:10
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 13:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 13:11
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 31s
- Log: OOMPAH-718__20260803T131051Z.jsonl
---
author: oompah
created: 2026-08-03 13:12
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 13:12
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-03 13:12
---
Understanding: task-level acyclicity can hide a cycle in authorized code reachability across sibling epics. I will trace dependency validation, nested-epic synchronization, integration queue health, and diagnostics; add deterministic cycle detection/repair or actionable blocking, regression tests, and focused verification.
---
author: oompah
created: 2026-08-03 13:16
---
Discovery: task-level cycle detection already exists in oompah/dependency_graph.py and server dependency mutation, while orchestrator queue readiness only checks one epic at a time. Existing OOMPAH-562/633 repair intentionally permits only landed/default or authoritative parent branches, rejecting unrelated sibling synchronization. I will add a deterministic container graph and route unsafe cycles to an explicit Needs Human repair state that preserves private heads and exact integrated SHAs; landed-parent cross-epic dependencies will not produce a cycle.
---
author: oompah
created: 2026-08-03 13:23
---
Implementation: added deterministic container reachability graph/SCC analysis in oompah/container_dependency_graph.py. Dependency mutation now rejects a new edge that closes a container cycle with path and repair metadata. Queue summaries expose cycle diagnostics. Orchestrator audits each project before claiming, routes only affected Ready rows to Needs Human with the exact prerequisite SHA and original private head, cancels only those queue rows, and leaves independent epic groups untouched. Added focused graph, API, and parallel-queue regressions.
---
author: oompah
created: 2026-08-03 13:25
---
Verification: focused suites pass (66 tests). The required make test gate exited before pytest during Make setup because astral-uv could not create its transient scope (DBus InvalidArgs: kernel thread). No full-gate tests ran; I will use the already provisioned interpreter with scripts/run-tests.sh isolation as an environment fallback, then recheck the final diff.
---
author: oompah
created: 2026-08-03 13:37
---
Verification: focused dependency/API/parallel suites pass (63 tests after final dashboard-summary assertion). Full project fallback via scripts/run-tests.sh parallel passed 15,094 tests, with 7 skipped, 1 expected xfail, and 43 warnings in 6:57. Direct make test could not start because its uv setup hit the host DBus transient-scope error before pytest.
---
author: oompah
created: 2026-08-03 13:43
---
Completion: Delivered container-level cycle detection and safe repair fencing. The graph reports deterministic multi-epic paths, affected Ready rows, exact prerequisite SHAs, and an authorized repair selection; dependency mutations return actionable 409s; queue/dashboard summaries expose diagnostics; integration audits route only affected rows to Needs Human without importing sibling work; CAS cancellation preserves newer private heads and independent queues. Focused suites pass (78 tests), and the full fallback gate passes (15,094 passed, 7 skipped, 1 xfailed); direct make test setup remains unavailable because astral-uv cannot create its DBus transient scope in this environment.
---
author: oompah
created: 2026-08-03 13:44
---
Implemented deterministic container-level dependency cycle detection, actionable queue/dashboard diagnostics, safe Needs Human repair routing, dependency mutation rejection, and compare-and-swap head fencing. Focused tests and full fallback gate pass.
---
author: oompah
created: 2026-08-03 13:44
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 168
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 32m 9s
- Log: OOMPAH-718__20260803T131216Z.jsonl
---
author: oompah
created: 2026-08-03 13:57
---
Live workaround applied to the Exocomp cycle. Promoted completed EXOCOMP-141 ancestry through common parent EXOCOMP-127 into EXOCOMP-134 at db7ca3ae, rebased/resubmitted EXOCOMP-171 at e826d0d5 (79 focused tests), and it integrated on attempt 1. Then fast-forwarded exact integrated SHA e826d0d5 through EXOCOMP-127 and EXOCOMP-129. EXOCOMP-142 now waits only for EXOCOMP-171 terminal audit, not code reachability.
---
author: oompah
created: 2026-08-03 14:07
---
Branch quality gate passed for `c9734b0cf5e7ce375b31350ee9543627b5facc0a` using `make test` in 403.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-03 14:08
---
YOLO: Merge conflict detected on MR #678. Rebase onto main and resolve conflicts.
---
author: oompah
created: 2026-08-03 14:08
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-03 14:08
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-08-03 14:09
---
Understanding: I am handling the review-branch merge conflict only. I will rebase OOMPAH-718 onto its target branch, resolve conflicts by preserving both branch intents, run focused affected tests, force-push with lease, and inspect the resulting review diff.
---
author: oompah
created: 2026-08-03 14:09
---
Discovery: rebasing the sole OOMPAH-718 commit onto origin/main produced one content conflict in oompah/server.py. The target branch contains adjacent dependency/decomposition validation changes, so I will reconcile the shared request paths rather than choosing either side wholesale.
---
author: oompah
created: 2026-08-03 14:10
---
Implementation: rebase conflict resolved in oompah/server.py. The merged queue summary retains OOMPAH-717 retry/backoff and generated-helper diagnostics while retaining OOMPAH-718 container-cycle fields, repair path, and cycle-priority wait reason. Rebase completed as c47cae954; no scope beyond conflict reconciliation.
---
author: oompah
created: 2026-08-03 14:10
---
Verification: resolved rebase passed focused serial coverage: scripts/run-tests.sh serial tests/test_container_dependency_graph.py tests/test_server_dependencies.py tests/test_integration_queue.py tests/test_parallel_epic_children.py — 82 passed in 13.39s. This covers container-cycle detection, dependency rejection, queue repair/retry behavior, and parallel epic integration diagnostics.
---
<!-- COMMENTS:END -->
