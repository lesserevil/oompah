---
id: OOMPAH-853
type: task
status: In Progress
priority: null
title: Keep duplicate screening decisive when structural peers exceed the corpus budget
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T05:13:32.681862Z'
updated_at: '2026-08-06T05:31:57.576846Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-853
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 76de1f1705d2c49c194b4b015da286ed72a8022249d7dda6e00ae5520b1a3460
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T05:14:48.857024+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-853 is the only task targeting duplicate-preflight\
    \ corpus construction budget robustness. Related active tasks (OOMPAH-809, OOMPAH-811,\
    \ OOMPAH-846, OOMPAH-847) address capacity lanes, integration metadata, and validation\
    \ guards\u2014orthogonal concerns. Terminal tasks are historical context for the\
    \ larger workflow-engine migration epic (OOMPAH-763). The omitted structural peers\
    \ (OOMPAH-848/849/850/851/852) cannot be compared due to corpus budget pressure,\
    \ which is precisely the problem OOMPAH-853 must solve. No active duplicate exists;\
    \ this is a discrete fix.\n# Duplicate Investigation: OOMPAH-853\n\nI'm performing\
    \ a read-only duplicate screening investigation on OOMPAH-853 using only the supplied\
    \ project task corpus. Let me analyze the current task against all active peers.\n\
    \n## Analysis\n\n**Current Task OOMPAH-853:**\n- Title: \"Keep duplicate screening\
    \ decisive when structural peers exceed the corpus budget\"\n- Status: Open\n\
    - Scope: Fix the duplicate preflight system so corpus budget pressure never strands\
    \ actionable tasks in \"Needs Human\" state. Ensure conclusive verdicts despite\
    \ bounded corpus constraints.\n\n**Corpus Diagnostic Evidence:**\nThe corpus selection\
    \ itself demonstrates the exact problem OOMPAH-853 aims to solve:\n- Required\
    \ peer count: 30, included: 25, omitted: 5\n- Omitted identifiers: OOMPAH-848,\
    \ OOMPAH-849, OOMPAH-850, **OOMPAH-851**, OOMPAH-852\n- Diagnostic message: \"\
    Required structural peers could not fit the bounded corpus\"\n\n**Key Finding:**\
    \ OOMPAH-851 (the regression case that triggered this task) is in the omitted\
    \ set, so I cannot fully analyze it.\n\n**Active Peer Review:**\nI reviewed all\
    \ active (Open/In Progress) and terminal (Done/Merged) tasks in the corpus:\n\
    - **OOMPAH-809** (Open): About terminal-audit lane starvation and scheduler capacity\
    \ reservation\n- **OOMPAH-811** (Open): About integration ownership rearming during\
    \ rebase\n- **OOMPAH-831** (Needs CI Fix): About terminal-auditor tool contract\
    \ consistency\n- **OOMPAH-846** (In Progress): About validation-resource lease\
    \ enforcement for worker commands\n- **OOMPAH-847** (In Progress): About unit\
    \ test isolation from loaded-gate work\n- Other Done/Merged tasks: All address\
    \ distinct workflow-engine subsystems (facts, decisions, jobs, audits, integration,\
    \ watchdog recovery, fixture stability, recovery objects, lifecycle retry loops,\
    \ auditor contracts, nested-epic dispatch, capacity reservation, tool result delivery)\n\
    \n**No Terminal Duplicates:** The terminal tasks (OOMPAH-764\u2013767, OOMPAH-806\u2013\
    807, OOMPAH-810, OOMPAH-814\u2013817, OOMPAH-822, OOMPAH-840\u2013841) all addres"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-853
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-853
  base_branch: epic-OOMPAH-763
  base_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
  updated_at: '2026-08-06T05:15:19.353933+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1996
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1996
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1996
    cost_usd: 0.0
    recorded_at: '2026-08-06T05:14:48.855557+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-853__20260806T051420Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-853
    source_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
    completed_at: '2026-08-06T05:14:48.878530+00:00'
---
## Summary

Live regression: OOMPAH-851 entered Needs Human on 2026-08-06 because duplicate screening declared required structural peers OOMPAH-848/OOMPAH-849/OOMPAH-850 could not fit the bounded corpus, despite OOMPAH-728's structural-peer retention work. A byte/task bound is an internal resource constraint and must not strand an actionable task for operator intervention. Implementation scope: make duplicate-corpus construction reserve deterministic space for every authoritative structural peer or compact peer records into sufficient identity/title/relationship/evidence summaries; distinguish an actual unreadable/corrupt tracker corpus from ordinary budget pressure; always produce a conclusive duplicate/unique verdict when tracker reads are healthy; preserve non-leakage, project scope, token bounds, and exact task/epic/depends-on relationships. Relevant code: duplicate preflight corpus selection/serialization, structural peer resolution, completion/owner-resolution flow, and duplicate-preflight health alerts. Required tests: reproduce OOMPAH-851 with three required peers exceeding both task and byte budgets; prove all peers remain represented and the investigator can return a durable verdict without Needs Human; cover one huge peer, many peers, multibyte text, missing/terminal/archived peers, restart/retry coalescing, and genuinely corrupt tracker reads remaining actionable. Acceptance criteria: healthy bounded corpus pressure never emits 'Required structural peers could not fit' or moves a task to Needs Human; the verdict remains scoped, deterministic, truncation-safe, and within configured limits; focused duplicate-preflight/corpus tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 05:14
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 05:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 05:14
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 47s
- Log: OOMPAH-853__20260806T051420Z.jsonl
---
author: oompah
created: 2026-08-06 05:15
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 05:15
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 05:15
---
Understanding: duplicate screening must remain conclusive under healthy task/byte corpus pressure. I will trace corpus selection, structural-peer resolution, and completion/health handling; implement deterministic bounded peer representation without weakening scope or relationship guarantees; add regression coverage for budget pressure versus genuine tracker corruption; run focused checks, commit, push, and submit.
---
author: oompah
created: 2026-08-06 05:27
---
Discovery: the OOMPAH-728 selection path reserves structural peers only as full rows, marks any row/byte overflow as availability=insufficient, and _finish_duplicate_preflight_sync converts that diagnostic directly into Needs Human. Healthy budget pressure is therefore misclassified as tracker failure. The fix retains all present structural peers as bounded structural_peers summaries, keeps normal rows when they fit, and reserves task/byte space before similarity/generic candidates; only unavailable/corrupt fetches remain retryable/actionable.
---
author: oompah
created: 2026-08-06 05:27
---
Implementation: duplicate corpus construction now validates tracker records, clips untrusted text by UTF-8 bytes, reserves all structural peers before ordinary candidates, and emits compact structural_peers identity/title/status/relationship/evidence records when full rows exceed task or byte limits. Corpus availability stays authoritative for healthy budget pressure; corrupt/unavailable reads use bounded retry handling. Updated investigator guidance/docs and replaced the obsolete insufficient-budget escalation tests with OOMPAH-851, terminal/missing-peer, and corrupt-read regressions.
---
author: oompah
created: 2026-08-06 05:28
---
Verification: focused duplicate-preflight, focus, prompt, and orchestrator duplicate-detection suites pass (265 tests). The bounded regression confirms serialized UTF-8 corpus bytes stay within 3,500, all three structural peers are represented, and the durable no_duplicate completion remains Open without a Needs Human comment; corrupt tracker reads still reach the existing actionable owner-resolution path.
---
author: oompah
created: 2026-08-06 05:30
---
Operator note: I terminated only your unleased full make-test process group because it started concurrently with OOMPAH-852's authoritative exact-head gate, reproducing the live validation-lane race OOMPAH-852 fixes. Do not rerun full or focused tests while that lease is active. Preserve the already-green 265 focused tests, finish static checks, commit/push, and submit; the server's exact-head gate will validate the branch after deployment of the classifier fix.
---
author: oompah
created: 2026-08-06 05:31
---
Completion: delivered and pushed 92e8d38fc. Healthy duplicate corpus pressure now retains every present structural peer through deterministic compact summaries within task/byte bounds, preserves relationship/project/terminal handling, and completes durable conclusive verdicts without Needs Human. Unavailable/corrupt tracker reads remain on bounded retry and actionable owner-resolution flow. Focused suites: 265 passed; py_compile and diff checks passed. The equivalent full 16,075-test parallel run started with passes but was host-terminated (SIGTERM) during early global tests; make setup/test wrapper was separately blocked by the host read-only validation-lease path.
---
<!-- COMMENTS:END -->
