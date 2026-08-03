---
id: OOMPAH-718
type: task
status: In Progress
priority: null
title: Detect and repair container-level cycles from cross-epic finish dependencies
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T13:10:18.934341Z'
updated_at: '2026-08-03T13:12:15.339771Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
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
oompah.agent_run_id: a29cdbfc-7ec4-4ae9-8f18-c57fe8093fc6
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
<!-- COMMENTS:END -->
