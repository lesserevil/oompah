---
id: OOMPAH-582
type: task
status: In Validation
priority: null
title: Satisfy legacy Done cross-epic dependencies after parent merge
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T04:39:46.196812Z'
updated_at: '2026-08-06T17:35:48.658084Z'
work_branch: OOMPAH-582
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/592
review_number: '592'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 25c9271d788a889a3576cb8aba9615a008b7c63f4bc224e416c9f3dd289047de
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T04:41:50.914772+00:00'
  matched_identifiers: []
  evidence: "Based on my investigation as a Duplicate Investigator, I have searched\
    \ through all active tasks in the `.oompah/tasks` directories:\n\n**Search Results:**\n\
    - **Open tasks:** Only OOMPAH-281 (GitHub Actions self-hosted runner setup) \u2014\
    \ unrelated\n- **Merged tasks:** 7 tasks, none related to dependencies or orchestrator\n\
    - **Backlog:** Only OOMPAH-282 (Unicode encoding bug) \u2014 unrelated  \n- **Archived\
    \ tasks:** 200+ historical tasks searched for patterns like \"orchestrator\",\
    \ \"integration\", \"dependency\", \"epic merge\", \"cross-epic\", \"satisfied\"\
    , \"integrate queue\", etc. \u2014 no matches found\n\n**Code Search:**\n- Searched\
    \ `oompah/orchestrator.py` for functions like `_integration_satisfied_dependencies`,\
    \ `integrated_sha`, `def.*integrat`, `def.*depend`, `def.*satisfied` \u2014 no\
    \ existing implementation found\n- This indicates the feature described in OOMPAH-582\
    \ is new work, not a fix for an existing mechanism\n\n**Conclusion:**\n\nOOMPAH-582\
    \ is a unique, first-of-its-kind task. It describes a specification for handling\
    \ legacy Done cross-epic dependencies after a parent epic merge (the concrete\
    \ case: after OOMPAH-459 merged and epic-OOMPAH-460 was rebased). The issue references\
    \ tasks (OOMPAH-483/484/459/460) that appear to be hypothetical/future test fixtures\
    \ rather than existing active tasks.\n\nNo active duplicate exists among any open,\
    \ merged, backlog, or archived tasks. This is original implementation work with\
    \ no prior solution to build upon.\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\
    \ Comprehensive search across all task states (.oompah/tasks/) found zero existing\
    \ tasks addressing Done cross-epic dependency satisfaction, legacy integration\
    \ records with missing integrated_sha, or operator-facing integration queue summary\
    \ corrections. Code search in orchestrator.py/server.py found no `_integration_satisfied_dependencies`\
    \ function or related integration-satisfied logic. OOMPAH-582 is an original implementation\
    \ tas"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: caacc9ea-0c2e-497f-b3cb-18e3d0da98c5
oompah.task_costs:
  total_input_tokens: 119988
  total_output_tokens: 6526
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 45022
      output_tokens: 4039
      cost_usd: 0.0
    sonnet:
      input_tokens: 74903
      output_tokens: 810
      cost_usd: 0.0
    opus:
      input_tokens: 63
      output_tokens: 1677
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 154
    output_tokens: 3524
    cost_usd: 0.0
    recorded_at: '2026-07-30T04:41:50.913363+00:00'
  - profile: default
    model: haiku
    input_tokens: 44868
    output_tokens: 515
    cost_usd: 0.0
    recorded_at: '2026-07-30T04:42:22.275478+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 74903
    output_tokens: 810
    cost_usd: 0.0
    recorded_at: '2026-07-30T04:43:15.175382+00:00'
  - profile: deep
    model: opus
    input_tokens: 63
    output_tokens: 1677
    cost_usd: 0.0
    recorded_at: '2026-07-30T04:48:25.398255+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-582__20260730T044038Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-582
    source_sha: 3aa2bd65bebf902b96e933e845352b1a8b98fbe7
    completed_at: '2026-07-30T04:41:50.923652+00:00'
  - run_id: OOMPAH-582__20260730T044207Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: chore
    source_branch: OOMPAH-582
    source_sha: 3aa2bd65bebf902b96e933e845352b1a8b98fbe7
    completed_at: '2026-07-30T04:42:22.278870+00:00'
  - run_id: OOMPAH-582__20260730T044252Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: chore
    source_branch: OOMPAH-582
    source_sha: 3aa2bd65bebf902b96e933e845352b1a8b98fbe7
    completed_at: '2026-07-30T04:43:15.178447+00:00'
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: OOMPAH-582
  head_sha: bbd48ada7abbd726e2ad6ae761a5037cdbea1e6f
  submitted_at: '2026-07-30T04:48:10.374087+00:00'
  updated_at: '2026-07-30T04:48:10.374087+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/592
oompah.review_number: '592'
oompah.work_branch: OOMPAH-582
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    no-auditor-audit-ba83e71f4e4d-1: '2026-07-30T14:12:32.507045+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-7520c8d7f6ad
    project_id: proj-14849f1b
    task_id: OOMPAH-582
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 720675a14cf2539cbbb8bf0aa1f078001c629588e8a2c121b2416760785dd739
    authorized_by:
      version: 1
      identity: lesserevil
      source: api
    reason: Operator re-evaluation confirmed implementation commit bbd48ada7 is an
      ancestor of origin/main and the task branch has already been consumed. The prior
      terminal audit failed only because of the forced-auditor transport bug; reopening
      implementation would duplicate landed work.
    created_at: '2026-07-30T17:14:28.511854+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-ba83e71f4e4d
    project_id: proj-14849f1b
    task_id: OOMPAH-582
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 720675a14cf2539cbbb8bf0aa1f078001c629588e8a2c121b2416760785dd739
    attempts:
    - version: 1
      attempt_id: attempt-5dc536ddd5f2
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 720675a14cf2539cbbb8bf0aa1f078001c629588e8a2c121b2416760785dd739
      created_at: '2026-07-30T04:55:36.406677+00:00'
      provider_id: prov-3c712bff
      model: nvidia/nvidia/nemotron-3-ultra
      started_at: '2026-07-30T04:55:36.406677+00:00'
      branch_key: OOMPAH-582
      ended_at: '2026-07-30T04:55:41.394020+00:00'
      failure_reason: 'unknown url type: ''/chat/completions'''
      next_retry_at: '2026-07-30T04:55:51.393988+00:00'
    - version: 1
      attempt_id: no-auditor-audit-ba83e71f4e4d-1
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 720675a14cf2539cbbb8bf0aa1f078001c629588e8a2c121b2416760785dd739
      verdict: fail
      failure_classification: no_auditor
      created_at: '2026-07-30T14:12:32.506872+00:00'
      completed_at: '2026-07-30T14:12:32.506872+00:00'
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-07-30T04:54:55.183299+00:00'
    updated_at: '2026-07-30T14:12:32.506872+00:00'
  - version: 1
    audit_id: audit-6db456fe5e16
    project_id: proj-14849f1b
    task_id: OOMPAH-582
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 720675a14cf2539cbbb8bf0aa1f078001c629588e8a2c121b2416760785dd739
    attempts:
    - version: 1
      attempt_id: attempt-339ecd6514f7
      target_state: Merged
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 720675a14cf2539cbbb8bf0aa1f078001c629588e8a2c121b2416760785dd739
      created_at: '2026-08-06T17:35:38.742660+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-06T17:35:38.742660+00:00'
      branch_key: OOMPAH-582
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-07-30T04:54:55.183299+00:00'
    updated_at: '2026-08-06T17:35:38.742660+00:00'
  - version: 1
    audit_id: audit-c9362f973f19
    project_id: proj-14849f1b
    task_id: OOMPAH-582
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9db0bedb89262cae833106e6baee3900031391ac6242968561ee7ff4432c5e9f
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-06T17:32:33.409407+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-5dc536ddd5f2
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 720675a14cf2539cbbb8bf0aa1f078001c629588e8a2c121b2416760785dd739
    created_at: '2026-07-30T04:55:36.406677+00:00'
    provider_id: prov-3c712bff
    model: nvidia/nvidia/nemotron-3-ultra
    started_at: '2026-07-30T04:55:36.406677+00:00'
    branch_key: OOMPAH-582
    ended_at: '2026-07-30T04:55:41.394020+00:00'
    failure_reason: 'unknown url type: ''/chat/completions'''
    next_retry_at: '2026-07-30T04:55:51.393988+00:00'
  - version: 1
    attempt_id: attempt-339ecd6514f7
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 720675a14cf2539cbbb8bf0aa1f078001c629588e8a2c121b2416760785dd739
    created_at: '2026-08-06T17:35:38.742660+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-06T17:35:38.742660+00:00'
    branch_key: OOMPAH-582
---
## Summary

Live reproduction: after OOMPAH-459 merged and epic-OOMPAH-460 was rebased to current main, OOMPAH-484 remains Ready to Integrate because dependency OOMPAH-483 is Done but its legacy integration record has state=working and no integrated_sha. The code is already reachable through OOMPAH-483's Merged parent epic OOMPAH-459 and current default branch, but _integration_satisfied_dependencies only permits the default-branch witness when the dependency itself is Merged/Archived. Implementation scope: in oompah/orchestrator.py, allow a terminal Done cross-epic dependency with missing/unreachable integrated_sha to use the current default-branch reachability witness only when its parent epic resolves from the same issue index and that parent is Merged or Archived. Preserve same-epic behavior and do not satisfy Done children of nonterminal/missing parents. Update the operator-facing integration queue summary in oompah/server.py to use the same rule so it does not keep reporting a false upstream-code blocker after the parent epic lands. Tests: add focused scheduler and API summary cases for Done child + Merged parent + default ref reachable, plus negative cases for parent Done/In Progress/missing and default ref not reachable. Acceptance criteria: OOMPAH-483 is considered satisfied for OOMPAH-484 only after OOMPAH-459 has terminal-landed and main is reachable from epic-OOMPAH-460; OOMPAH-484 becomes claimable; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 04:40
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 04:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 04:41
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 42, Tool calls: 21
- Tokens: 154 in / 3.5K out [3.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 16s
- Log: OOMPAH-582__20260730T044038Z.jsonl
---
author: oompah
created: 2026-07-30 04:42
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 04:42
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-30 04:42
---
Agent completed successfully in 19s (45383 tokens)
---
author: oompah
created: 2026-07-30 04:42
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 1
- Tokens: 44.9K in / 515 out [45.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 19s
- Log: OOMPAH-582__20260730T044207Z.jsonl
---
author: oompah
created: 2026-07-30 04:42
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-582`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-30 04:42
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-30 04:42
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-30 04:43
---
Agent completed successfully in 28s (75713 tokens)
---
author: oompah
created: 2026-07-30 04:43
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 3
- Tokens: 74.9K in / 810 out [75.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 28s
- Log: OOMPAH-582__20260730T044252Z.jsonl
---
author: oompah
created: 2026-07-30 04:43
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-582`. Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-30 04:43
---
Reproduced the live OOMPAH-483 shape and implemented the narrow merged-parent fallback across dependency satisfaction, stale-queue rebase detection, and operator-facing wait summaries. Focused dependency/queue tests pass (24), including missing/nonterminal parent and unreachable-default negative cases. Running make test.
---
author: oompah
created: 2026-07-30 04:43
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-30 04:43
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-30 04:45
---
Understanding: extend the terminal cross-epic dependency satisfaction rule in two places so a legacy Done child no longer blocks the sibling epic queue once its parent epic has landed on default. Plan: (1) in oompah/orchestrator.py _integration_satisfied_dependencies, allow the default-branch reachability witness for a Done cross-epic dep when its parent (resolved via issues_by_alias, and whose identifier != epic_aliases) is Merged or Archived; keep same-epic semantics unchanged and require unreachable/missing integrated_sha before the fallback. (2) mirror in oompah/server.py _integration_queue_summary so that a Done child of a Merged/Archived parent is not reported as an unreachable upstream-code blocker. Add scheduler + summary tests for Done+Merged-parent positive case and negatives (parent Done/In Progress/missing, default ref unreachable). Focus: chore.
---
author: oompah
created: 2026-07-30 04:48
---
Fixed live cross-epic queue blocker: legacy Done children without integrated_sha may use default-branch ancestry only after their parent epic has Merged/Archived. Updated stale-rebase detection and wait summaries; negative cases remain blocked. Focused tests: 24 passed. Full make test: 13,694 passed, 7 skipped; terminal mutation scan passed. Commit bbd48ada7 pushed.
---
author: oompah
created: 2026-07-30 04:48
---
Run #3 [attempt=3, profile=deep, role=deep -> Claude/opus]
- Turns: 0, Tool calls: 38
- Tokens: 63 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 32s
- Log: OOMPAH-582__20260730T044357Z.jsonl
---
author: oompah
created: 2026-07-30 04:54
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 04:55
---
Auditor dispatched (attempt #1, candidate: prov-3c712bff/nvidia/nvidia/nemotron-3-ultra)
---
author: oompah
created: 2026-07-30 04:55
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 04:55
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2s
- Log: OOMPAH-582__20260730T045539Z.jsonl
---
author: oompah
created: 2026-07-30 04:55
---
Auditor attempt ended: unknown url type: '/chat/completions'. A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-07-30 14:12
---
Needs Human — Done audit requires operator input.

No independent auditor candidate is available for this audit (All eligible auditor candidates were already attempted for this audit.). Configure the `auditor` role with at least one healthy provider/model that is independent of the task contributors, then move the task back to Open to retry.
---
author: oompah
created: 2026-07-30 17:14
---
Override by lesserevil: terminal transition to Merged applied by project owner.

Reason: Operator re-evaluation confirmed implementation commit bbd48ada7 is an ancestor of origin/main and the task branch has already been consumed. The prior terminal audit failed only because of the forced-auditor transport bug; reopening implementation would duplicate landed work.
---
author: oompah
created: 2026-07-30 17:14
---
Re-evaluated against current git ancestry. Commit bbd48ada7 is already on main, so the landed task is marked Merged by project-owner override.
---
author: oompah
created: 2026-08-06 17:35
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-06 17:35
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
