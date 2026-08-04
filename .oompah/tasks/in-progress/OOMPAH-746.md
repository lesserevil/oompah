---
id: OOMPAH-746
type: bug
status: In Progress
priority: 1
title: Resolve terminal-audit evidence from canonical epic branches when work_branch
  is absent
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T00:40:18.391859Z'
updated_at: '2026-08-04T00:44:33.564475Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1435d8d231ea47878cdbfb3e8bec02bd7c390370d729fd2852567f034a214a0e
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T00:42:31.989989+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed all 32 similarity candidates in the corpus.\
    \ All peer tasks are archived/completed. Closest related tasks (OOMPAH-163 on\
    \ epic-branch dispatch validation; OOMPAH-165 on epic landing detection) address\
    \ distinct orchestration problems, not terminal-audit evidence resolution for\
    \ missing work_branch metadata. OOMPAH-746's requirement to derive canonical epic\
    \ branch names from issue type/parent/project metadata during terminal audit has\
    \ no precedent in the provided task history. This is a unique bug fix addressing\
    \ EXOCOMP-130's exhausted audit attempts.\nI'm investigating whether OOMPAH-746\
    \ is a duplicate of an existing task. Let me carefully review the provided task\
    \ corpus.\n\n## Analysis\n\n**Current task (OOMPAH-746):**\n- Status: Open\n-\
    \ Type: Bug\n- Scope: Resolve terminal-audit evidence from canonical epic branches\
    \ when work_branch metadata is absent\n- Triggered by: EXOCOMP-130 (exhausted\
    \ terminal-audit attempts because evidence resolution only tried origin/EXOCOMP-130,\
    \ ignoring origin/epic-EXOCOMP-130)\n- Key requirement: Derive correct epic branch\
    \ name from issue type, parent, project, and transition metadata for terminal\
    \ audit\n\n**Corpus analysis:**\n\nThe provided task corpus contains 32 similarity\
    \ candidates, all in terminal states (Archived). Key observations:\n\n1. **No\
    \ active open tasks match**: Only OOMPAH-746 itself is Open; all 31 peer candidates\
    \ are Archived\n2. **Related but distinct tasks**: \n   - OOMPAH-162, OOMPAH-163,\
    \ OOMPAH-165: Address epic landing/dispatch issues, but not terminal-audit evidence\
    \ resolution\n   - OOMPAH-166-171: Standardize epic workflow strategies; orthogonal\
    \ to evidence resolution\n   - OOMPAH-172-183: Release-addendum implementation;\
    \ completely different feature\n   - OOMPAH-186: CLI source-reference commands;\
    \ unrelated\n   - OOMPAH-270: Git lock retry logic; unrelated\n\n3. **Distinction\
    \ from closest candidates**:\n   - OOMPAH-163 (\"Allow generated epic target branches\
    \ through dispatch\") addresses validator rejection of epic-* branches during\
    \ dispatch, not terminal-audit evidence resolution\n   - OOMPAH-165 (\"Fix shared\
    \ epic landed detection\") fixes landing detection logic, not evidence resolution\
    \ for missing work_branch\n\n**Conclusion**: OOMPAH-746 addresses a specific bug\
    \ where terminal-audit evidence resolution fails when `work_branch` metadata is\
    \ absent and requires deriving the canonical epic branch name from issue metadata.\
    \ No existing archived task covers this specific evidence-resolution requirement.\n\
    \n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMa"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: c639d605-b673-4f1f-91f5-2f5a6a51e49f
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2384
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2384
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2384
    cost_usd: 0.0
    recorded_at: '2026-08-04T00:42:31.989330+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-746__20260804T004146Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-746
    source_sha: 4ea94b151a09758c57a93c8710c05f28a49bcc2a
    completed_at: '2026-08-04T00:42:31.995844+00:00'
---
## Summary

Triggered by: EXOCOMP-130

Live reproduction: EXOCOMP-130 exhausted all terminal-audit attempts before auditor launch because its task detail has no work_branch and evidence resolution tried only origin/EXOCOMP-130. The canonical branch origin/epic-EXOCOMP-130 exists at 7bf5506c, so valid immutable evidence is available but the resolver derives the wrong ref. Implementation scope: make terminal-audit staging resolve shared and nested epic branch names from authoritative issue type, parent, project, and persisted transition metadata; persist the exact work branch and immutable SHA when requesting a terminal transition; verify the remote ref and fail closed on ambiguity; distinguish absent metadata, deleted branches, and provider failures; and make corrected rearm/restart idempotent without reopening implementation. Preserve the immutable-SHA recovery delivered by OOMPAH-671. Relevant code includes terminal-audit staging and evidence collection in oompah/orchestrator.py plus project branch-resolution and transition metadata helpers. Required tests: reproduce EXOCOMP-130 where origin/ID is absent but origin/epic-ID exists; cover nested epics, exact SHA snapshotting, deleted branches with retained immutable evidence, ambiguous refs, restart/rearm, and cross-project naming. Acceptance criteria: a terminal request for an epic with absent work_branch resolves and audits the canonical epic ref exactly once; unsafe ambiguity remains blocked with an actionable diagnosis; existing deleted-branch recovery stays green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 00:41
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 00:41
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 00:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.4K out [2.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 18s
- Log: OOMPAH-746__20260804T004146Z.jsonl
---
author: oompah
created: 2026-08-04 00:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 00:44
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-04 00:44
---
**Understanding**: This is a terminal-audit resolution bug where evidence collection fails to find canonical epic branches (e.g., origin/epic-EXOCOMP-130) when work_branch is absent. The resolver currently only tries origin/ISSUE-ID and fails. I need to:

1. Enhance terminal-audit staging to resolve epic branch names (origin/epic-ID for standard issues, origin/epic-parent-ID for nested epics)
2. Persist exact work_branch and immutable SHA when requesting terminal transitions
3. Verify remote refs and fail safely on ambiguity
4. Handle absent metadata, deleted branches, and provider failures gracefully
5. Ensure rearm/restart is idempotent

**Planned approach**:
- Examine oompah/orchestrator.py terminal-audit staging and evidence collection logic
- Find branch-resolution and transition metadata helpers
- Implement canonical epic branch resolution using issue type/parent/project metadata
- Add tests covering EXOCOMP-130 scenario, nested epics, deleted branches, ambiguity
- Preserve immutable-SHA recovery from OOMPAH-671
---
<!-- COMMENTS:END -->
