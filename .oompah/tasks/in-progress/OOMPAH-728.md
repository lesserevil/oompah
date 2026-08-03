---
id: OOMPAH-728
type: bug
status: In Progress
priority: 1
title: Keep structurally relevant peers in duplicate-screening corpus
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T16:19:05.113116Z'
updated_at: '2026-08-03T16:25:59.499502Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: aea388b18a2c0faefa7f6c16fe1e122e4f6edc0ef800d6cd8f961e34bff6159e
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T16:21:03.011564+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: This is a new, project-specific regression about the\
    \ Duplicate Investigator's corpus construction and evidence retention. No existing\
    \ task in the current project corpus addresses corpus builder relevance selection,\
    \ structurally significant peer retention, or the EXOCOMP-216/EXOCOMP-221 regression.\
    \ Related archived tasks (OOMPAH-10 through OOMPAH-175) focus on webhooks, dashboard,\
    \ intake validation, and epic workflows\u2014entirely different subsystems. OOMPAH-728\
    \ requires focused implementation work on a previously untracked issue.\nI need\
    \ to investigate whether OOMPAH-728 is a duplicate of an existing task in the\
    \ project. Let me analyze this carefully.\n\n## Understanding OOMPAH-728\n\nThis\
    \ issue describes a production regression in the Duplicate Investigator's corpus\
    \ construction:\n- Agents screening EXOCOMP-216 and EXOCOMP-221 returned inconclusive\
    \ results\n- The corpus omitted active sibling tasks needed for comparison\n-\
    \ Agents exhausted retry budget and tasks were moved to Needs Human\n- The fix\
    \ requires: retaining structurally relevant peers, preventing unreachable loopback\
    \ calls, providing actionable diagnostics\n\nThis is specifically about the **duplicate-screening\
    \ corpus builder** - how it selects and prioritizes which tasks to include when\
    \ investigating whether a task is a duplicate.\n\n## Reviewing the Project Task\
    \ Corpus\n\nI've reviewed the provided authoritative task corpus containing all\
    \ project tasks. The corpus includes:\n\n**Active/Open tasks:**\n- OOMPAH-728\
    \ (current task - Open)\n\n**Archived/Completed tasks:**\n- OOMPAH-10 through\
    \ OOMPAH-175: Various infrastructure, dashboard, intake, and epic workflow fixes\n\
    - None of these address corpus construction for duplicate screening\n- None reference\
    \ the Duplicate Investigator's evidence gathering\n- None address the regression\
    \ with EXOCOMP-216/EXOCOMP-221\n\n**Key searches:**\n- \"corpus\" - appears only\
    \ in OOMPAH-728\n- \"duplicate.*screen\" or \"screening\" - appears only in OOMPAH-728\n\
    - \"EXOCOMP-216\" or \"EXOCOMP-221\" - appears only in OOMPAH-728\n- \"structurally\
    \ relevant peers\" - appears only in OOMPAH-728\n\nThe closest related task is\
    \ OOMPAH-682 (referenced in the acceptance criteria about investigators receiving\
    \ enough evidence), but it doesn't appear in the corpus and likely addresses a\
    \ different acceptance criterion.\n\n## Conclusion\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: This\
    \ is a new, project-specific regression about the Duplicate Investigator's corpus\
    \ construction and evidence retenti"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: bf01667e-b8e8-43ec-b76b-e9106d99b356
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1698
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1698
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1698
    cost_usd: 0.0
    recorded_at: '2026-08-03T16:21:03.010806+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-728__20260803T162028Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-728
    source_sha: d510748342777dd4748070d83391ffb0eae40091
    completed_at: '2026-08-03T16:21:03.049403+00:00'
---
## Summary

Triggered by: EXOCOMP-216

Production regression observed on 2026-08-03 while screening EXOCOMP-216 and EXOCOMP-221. Three independent Duplicate Investigator runs for each task returned inconclusive because the injected tracker-backed corpus omitted the active sibling tasks needed for comparison. The agents explicitly named the missing peers (EXOCOMP-209 and EXOCOMP-213 through EXOCOMP-218 for EXOCOMP-216; EXOCOMP-219 through EXOCOMP-224 for EXOCOMP-221). One run then tried the scoped task CLI at http://localhost:8090 even though its sandbox had no reachable server. Both valid tasks exhausted the bounded retry budget and were moved to Needs Human. This violates OOMPAH-682's acceptance criterion that investigators receive enough authoritative active-task evidence to reach a verdict.

Implementation scope:
- Reproduce corpus construction for EXOCOMP-216 and EXOCOMP-221 against a project with more tasks than the corpus budget.
- Make relevance selection retain structurally relevant active peers before generic truncation: parent/children/siblings, declared dependencies and hard-start dependencies, and title/description similarity candidates.
- Include enough task description and relevant comment evidence for a conclusive comparison, while retaining deterministic size bounds and treating all task text as untrusted.
- Do not instruct or rely on a sandboxed investigator to query an unreachable loopback service; either make the injected corpus self-sufficient or provide a supported authenticated read-only transport and advertise only capabilities actually available.
- Expose an actionable diagnostic when required peers cannot fit the corpus instead of consuming three indistinguishable model retries.

Required tests:
- Large-corpus regressions modeled on EXOCOMP-216 and EXOCOMP-221 prove every same-parent sibling and dependency relevant to screening is present.
- Deterministic budget tests prove unrelated tasks are evicted before structurally relevant peers.
- A network-disabled investigator prompt remains self-sufficient and does not require CLI fallback.
- Corpus entries preserve status, description, and bounded relevant comments.
- Existing prompt-injection, revision-fingerprint, late-claim, retry, and owner-resolution tests continue to pass.
- Run focused duplicate-preflight/prompt tests and make test.

Acceptance criteria:
- Each reproduced task reaches a conclusive screening verdict in one normal run using only supplied evidence.
- No valid task reaches Needs Human solely because relevant active peers were dropped by corpus selection.
- Corpus size remains bounded, deterministic, project-scoped, and safe for untrusted task text.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 16:20
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 16:20
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 16:21
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 41s
- Log: OOMPAH-728__20260803T162028Z.jsonl
---
author: oompah
created: 2026-08-03 16:21
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 16:21
---
Focus: Security Auditor
---
author: oompah
created: 2026-08-03 16:22
---
Understanding: I will trace duplicate-preflight corpus construction and investigator prompt generation, reproduce the large-project sibling/dependency omission, then implement deterministic structural relevance and bounded evidence while preserving untrusted-text isolation and network-disabled self-sufficiency. I will add regression tests, run focused checks and the Makefile gate, then commit, push, and submit.
---
author: oompah
created: 2026-08-03 16:25
---
Discovery: _duplicate_preflight_task_corpus currently sorts all scoped tasks by state/identifier, then truncates at 100 tasks and breaks on the first byte overflow. It ignores parent/child/sibling/dependency relationships and description similarity. Issue already carries parent_id, blocked_by, and start_blocked_by, so the fix can rank authoritative tracker records without worker checkout or network fallback.
---
<!-- COMMENTS:END -->
