---
id: OOMPAH-653
type: bug
status: Open
priority: 1
title: Make terminal-audit success and owner override retire every duplicate record
  and alert
parent: null
children: []
blocked_by:
- OOMPAH-652
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T09:02:42.727629Z'
updated_at: '2026-07-31T09:07:06.031572Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ecc261f5676ea5d8b1af31234c7a36146ba4f7293126bb4d4a497b5524d88565
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T09:06:39.815250+00:00'
  matched_identifiers: []
  evidence: "Based on my investigation as a Duplicate Investigator, I need to determine\
    \ whether OOMPAH-653 is a duplicate of an existing issue.\n\n## Investigation\
    \ Summary\n\nI conducted a comprehensive search across the project's task tracker\
    \ for similar issues:\n\n**Search queries executed:**\n- Keywords: \"terminal-audit\"\
    , \"override\", \"alert\", \"reconciliation\", \"duplicate record\", \"no_independent_candidate\"\
    \n- Task references from the issue: OOMPAH-643, OOMPAH-644, OOMPAH-648\n- Code\
    \ files mentioned: terminal_audit.py, terminal_transition_coordinator.py, orchestrator.py\n\
    \n**Results:**\n- **Open tasks**: Only OOMPAH-281 exists (unrelated - GitHub Actions\
    \ self-hosted runner setup)\n- **Merged tasks** (OOMPAH-271 through OOMPAH-280):\
    \ All are rebase/git management tasks for epic branches\n- **Archived tasks**\
    \ (OOMPAH-1 through OOMPAH-270): Searched for audit, override, alert, reconciliation\
    \ keywords - no matches\n\n**Key findings:**\n1. The issue references specific\
    \ regressions (OOMPAH-643, OOMPAH-644, OOMPAH-648) which do not exist as native\
    \ oompah tasks in `.oompah/tasks/`\n2. No active or completed task covers the\
    \ scope described in OOMPAH-653:\n   - Enforcing one canonical live audit identity\
    \ per fingerprint\n   - Making pass/override atomic and idempotent  \n   - Canceling/superseding\
    \ duplicate sibling audit records\n   - Clearing stale alerts after override\n\
    \   - Preventing reconciliation from recreating audits\n3. The core audit/alert\
    \ system files mentioned (terminal_audit.py, terminal_transition_coordinator.py,\
    \ etc.) exist in the codebase but have no corresponding bug/fix tasks\n\n**Conclusion:**\n\
    OOMPAH-653 describes unique regressions in terminal audit handling that have not\
    \ been previously tracked or completed.\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\
    \ Comprehensive search across all task states (.oompah/tasks open/merged/archived)\
    \ using keywords from the issue title and description (terminal-audit, override,\
    \ aler"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 4206da83-8b1f-4870-89a2-03972f40bea8
oompah.task_costs:
  total_input_tokens: 186
  total_output_tokens: 5534
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 186
      output_tokens: 5534
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 186
    output_tokens: 5534
    cost_usd: 0.0
    recorded_at: '2026-07-31T09:06:39.814175+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-653__20260731T090421Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-653
    source_sha: 8fd133e26aa2823ab68cde2a42b446933142b614
    completed_at: '2026-07-31T09:06:39.833015+00:00'
---
## Summary

Two live regressions remained after OOMPAH-643 merged. First, OOMPAH-648 audit attempt audit-db48e6cb6d3e recorded Audit PASS with safe evidence at 08:37, but another audit for the same terminal transition was dispatched at 08:38, retried, exhausted candidates, and moved the already-passed task to Needs Human. Second, OOMPAH-644 received an authorized owner override to Merged (override-b9bd25c5c20a), yet terminal_audit:no_independent_candidate for the superseded audit remained an error through multiple ticks and a full service restart. Implementation scope: enforce one canonical live audit identity per project/task/target-state/evidence fingerprint; make pass/override atomic and idempotent; cancel/supersede all sibling pending or in-progress records; prevent reconciliation from recreating an audit for the same applied fingerprint; remove their actionable alert identities and stale pending timestamps from health/state while retaining historical counters. Close races among auditor result persistence, task status movement, reconcile scans, owner override, and restart recovery. Relevant files: terminal_transition_coordinator.py, orchestrator audit scan/dispatch/result paths, terminal audit persistence/observability/health, state alert aggregation, and native task status reconciliation. Required deterministic tests: barrier between PASS persistence and reconcile scan; duplicate records already queued/running when PASS lands; override concurrent with no-candidate routing; restart after pass/override; repeated callbacks; task changes fingerprint after completion creates exactly one new audit; project isolation. Acceptance: OOMPAH-648-style PASS cannot be followed by a second audit or Needs Human, OOMPAH-644-style override immediately clears all superseded actionable alerts and stays clear across restart, historical evidence remains queryable, focused audit race tests, terminal mutation scan, and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 09:03
---
Post-override state proof: terminal_audit health reports pending=0, in_progress=0, failure_count=0, degraded=false, yet state alerts still emits terminal_audit:no_independent_candidate for both superseded OOMPAH-644 and OOMPAH-648 audits across ticks/restart. Alert invalidation is therefore diverging from the canonical health/audit record lifecycle.
---
author: oompah
created: 2026-07-31 09:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 09:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 09:06
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 53, Tool calls: 28
- Tokens: 186 in / 5.5K out [5.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 21s
- Log: OOMPAH-653__20260731T090421Z.jsonl
---
<!-- COMMENTS:END -->
