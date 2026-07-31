---
id: OOMPAH-588
type: epic
status: In Review
priority: 1
title: Finish safe repository hygiene and maintenance correctness
parent: OOMPAH-584
children:
- OOMPAH-600
- OOMPAH-601
- OOMPAH-602
- OOMPAH-603
blocked_by: []
start_blocked_by: []
labels:
- epic:rebased
assignee: null
created_at: '2026-07-30T14:13:46.482910Z'
updated_at: '2026-07-31T05:25:12.649909Z'
work_branch: epic-OOMPAH-588
target_branch: epic-OOMPAH-584
review_url: https://github.com/lesserevil/oompah/pull/602
review_number: '602'
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-d986f94b1463: '2026-07-31T05:09:14.294912+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-324180823f32
    project_id: proj-14849f1b
    task_id: OOMPAH-588
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cff28373e3c1ee4569653cad01553f25c79d3bef7dd3dd6f38b99c5b27c00ae1
    attempts:
    - version: 1
      attempt_id: attempt-d986f94b1463
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: cff28373e3c1ee4569653cad01553f25c79d3bef7dd3dd6f38b99c5b27c00ae1
      created_at: '2026-07-31T05:03:04.101670+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T05:03:04.101670+00:00'
      branch_key: OOMPAH-588
      verdict: pass
      completed_at: '2026-07-31T05:09:14.294662+00:00'
      ended_at: '2026-07-31T05:09:14.294662+00:00'
    requested_by:
      version: 1
      identity: orchestrator
    previous_state: Open
    created_at: '2026-07-31T05:02:58.950383+00:00'
    updated_at: '2026-07-31T05:09:14.294662+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-d986f94b1463
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cff28373e3c1ee4569653cad01553f25c79d3bef7dd3dd6f38b99c5b27c00ae1
    created_at: '2026-07-31T05:03:04.101670+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T05:03:04.101670+00:00'
    branch_key: OOMPAH-588
oompah.task_costs:
  total_input_tokens: 90
  total_output_tokens: 3061
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 90
      output_tokens: 3061
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 90
    output_tokens: 3061
    cost_usd: 0.0
    recorded_at: '2026-07-31T05:09:36.128152+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/602
oompah.review_number: '602'
oompah.work_branch: epic-OOMPAH-588
oompah.target_branch: epic-OOMPAH-584
---
## Summary

Goal

Finish aggressive but safe worktree/branch pruning and remove maintenance errors/noise that obscure real faults. Reuse OOMPAH-581, preserve dirty or unmerged work, repair project-scoped merged-label maintenance, and make cleanup outcomes measurable.

Relevant context

The managed oompah repository retained 20 registered worktrees, 117 local branches, and 67 remote branches. Cleanup itself reported no fatal error, but emitted repeated terminal-branch ownership warnings and a slow tick; merged_labels rejected OOMPAH-476 for missing project_id. OOMPAH-581 is already implemented and Ready to Integrate.

Acceptance criteria

Safe terminal artifacts are pruned on schedule; dirty/unmerged/shared-owner work is preserved; ownership skips are aggregated instead of warning-flooded; cleanup latency and categorized skip counts are visible; merged-label maintenance always resolves project scope without unsafe legacy fallback; focused and complete gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 14:20
---
Children are accepted and open; activate the hygiene recovery epic.
---
author: oompah
created: 2026-07-31 01:00
---
Operator recovery for the live nested-epic queue deadlock: rebased origin/epic-OOMPAH-588 from 89dfc1881 onto current parent origin/epic-OOMPAH-584 d62dd4cff and force-pushed with an exact lease at b4959703e. The three OOMPAH-602 commits replayed cleanly; adjusted one maintenance-scope test mock for the newer authoritative landing-ref refresh. Focused merged-label scope and rollup verification: 33 passed; terminal mutation scan passed.
---
author: oompah
created: 2026-07-31 05:03
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 05:03
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 05:03
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 05:09
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- epic_head: 869005b387d5bcf2ad76eac66a608ece7f235fd9
- parent_head: b1425f6be8a8914c336d4dcb748ad4e10dc7a372
- child_OOMPAH-600_commits: 67c67ffa6, 6b8310896
- child_OOMPAH-601_commits: 5176c9e47, 8553b181c
- child_OOMPAH-602_commits: b4959703e, 9f6f47375, 05abc1144
- child_OOMPAH-603_commits: 869005b38, 3a1c79ed8
- diff_stat: 19 files, +2644/-875 versus parent
- key_added_modules: oompah/repo_hygiene.py, docs/repository-health-operations.md
- config_env_vars: OOMPAH_REPO_HYGIENE_SAFELY_PRUNABLE_AGE_SECONDS, _COUNT_WARNING, _COUNT_CRITICAL, _CLEANUP_ERROR_THRESHOLD
- regression_tests_added: test_repo_hygiene.py, test_orchestrator_repo_hygiene.py, test_merged_labels_scope.py (+405 lines), test_dashboard_repo_hygiene_health.py, test_orchestrator_handlers.py (aggregation), test_task_handoff.py, test_pytest_parallel.py
- ac1_terminal_pruning: OOMPAH-603 thresholds + OOMPAH-600 scoped mutations
- ac2_preservation: WorktreeCategory/BranchCategory dirty/unmerged/shared_owner categories retained in healthy_retained()
- ac3_aggregation: _delete_owned_issue_branch_locked returns (changed, skip_reason); shared_epic_branch skipped silently; per-run summary aggregated in _maintenance_status[worktree_cleanup][skipped_branches]
- ac4_visibility: OOMPAH-603 dashboard.html hygiene panel + repo_hygiene.RepoHygieneHealth.to_dict
- ac5_scope_resolution: _resolve_issue_project_id fail-closed on ambiguity; explicit project-mismatch rejected; legacy tracker never called under managed projects (test_managed_scope_never_calls_legacy_tracker)
- ac6_gates: OOMPAH-600 submission: 13914 passed / 7 skipped; OOMPAH-603 submission: full Makefile gate green; operator recovery: 33 focused + terminal mutation scan passed
---
author: oompah
created: 2026-07-31 05:09
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 60
- Tokens: 90 in / 3.1K out [3.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 6m 24s
- Log: OOMPAH-588__20260731T050322Z.jsonl
---
author: oompah
created: 2026-07-31 05:18
---
Operator self-hosting recovery: rebased origin/epic-OOMPAH-588 from 869005b38 onto current parent origin/epic-OOMPAH-584 145b6b67e, resolving cleanup-result and terminal-metrics overlaps by preserving both newer contracts. Added conflict regression commit c2549a76d. Focused repository hygiene/projects/config/merged-label suite: 530 passed. Terminal mutation scan passed. Pushed exact head c2549a76d; parent comparison 0 behind / 10 ahead; all four terminal child refs refreshed to contained rebased heads.
---
author: oompah
created: 2026-07-31 05:24
---
Operator recovery validation completed on exact rebased head c2549a76d08cd51eb979aa710c4c9778b7468a26. Full Makefile gate passed: 14,163 passed, 7 skipped, 1 xfailed, 56 warnings in 255.21s. Terminal-audit mutation scan also passed. The old runtime continues to defer PR creation using stale pre-rebase integration evidence, so the approved operator fallback will open the nested PR to epic-OOMPAH-584 from this exact validated head.
---
<!-- COMMENTS:END -->
