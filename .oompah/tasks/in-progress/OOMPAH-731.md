---
id: OOMPAH-731
type: task
status: In Progress
priority: null
title: Complete direct epic rebases without self-invalidating submission
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T17:45:33.391967Z'
updated_at: '2026-08-03T18:33:57.738668Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 721a65e211683c1283e69f2cb0f9320f456417f3ce7ea311ecedfd6e7ac233bc
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T17:51:11.546626+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed all 175 peer tasks in the supplied corpus. OOMPAH-731\
    \ describes a specific maintenance task submission failure in epic rebase workflows\
    \ (self-invalidating after successful force-with-lease publish). The closest related\
    \ archived tasks (OOMPAH-162 through OOMPAH-175) address epic workflow orchestration,\
    \ strategy consolidation, and release infrastructure, but none cover the maintenance\
    \ completion path or worktree-head validation issue described in OOMPAH-731. No\
    \ active duplicate exists in the current task tracker.\n# Duplicate Investigator\
    \ Analysis: OOMPAH-731\n\nI have reviewed the supplied project task corpus against\
    \ the current task OOMPAH-731 (\"Complete direct epic rebases without self-invalidating\
    \ submission\").\n\n**Corpus Review Summary:**\n\nThe current task corpus contains\
    \ OOMPAH-731 (Open) and 175 other tasks, of which all peer tasks (OOMPAH-1 through\
    \ OOMPAH-175) are in terminal states (Archived, Done, or Merged). Per the duplicate\
    \ screening requirements, terminal-state tasks are excluded from duplication analysis\
    \ as historical context rather than active duplicate targets.\n\n**Scope Match\
    \ Analysis:**\n\nOOMPAH-731 addresses a specific failure mode in the epic rebase\
    \ maintenance workflow:\n- Direct epic maintenance tasks (like EXOCOMP-244) successfully\
    \ rebase and publish epics via force-with-lease\n- Task submission then enters\
    \ ordinary child integration, where the worktree-head validator rejects the submission\n\
    - The validator compares the pre-rebase preserved epic checkout against the newly\
    \ published epic ref and fails\n\nThe closest archived tasks touching related\
    \ systems:\n- **OOMPAH-162-165**: Epic workflow fixes (stacked children, epic\
    \ landing detection, shared strategy consolidation) \u2014 all Archived\n- **OOMPAH-160**:\
    \ Atomic task writes and corrupt-file handling \u2014 Archived  \n- **OOMPAH-166-175**:\
    \ Epic strategy removal and release addendum infrastructure \u2014 all Archived\n\
    \nNone of these archived tasks describe the self-invalidating submission problem\
    \ for direct epic maintenance tasks, and the corpus contains no active (Open/In\
    \ Progress) duplicate.\n\n---\n\nFocus handoff: duplicate_detector\n\nDuplicate\
    \ preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: Reviewed all 175\
    \ peer tasks in the supplied corpus. OOMPAH-731 describes a specific maintenance\
    \ task submission failure in epic rebase workflows (self-invalidating after successful\
    \ force-with-lease publish). The closest related archived tasks (OOMPAH-162 through\
    \ OOMPAH-175) address epic workflow orchestration, strategy consolidation"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: a4a1e2ba-7aee-4bb2-a09e-da49dca57f3b
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1382
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1382
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1382
    cost_usd: 0.0
    recorded_at: '2026-08-03T17:51:11.544863+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-731__20260803T175013Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-731
    source_sha: f035aa3e64db9e6c71e6538c0c4fd7fcffa2de8c
    completed_at: '2026-08-03T17:51:11.556260+00:00'
---
## Summary

Live reproduction: EXOCOMP-244 is an auto-filed direct rebase task for epic-EXOCOMP-135. Its implementation agent correctly rebased the shared epic onto origin/main, verified the patch series with range-diff, and force-pushed the published epic from 333c3b81 to 98e26f09. The subsequent task submission entered ordinary child integration, whose worktree-head validator compared the intentionally pre-rebase preserved epic checkout with the newly published epic ref and rejected the task. This leaves a successful maintenance task Open with an integration_retry alert and invites duplicate work.\n\nImplementation scope:\n- Give direct shared-epic maintenance/rebase tasks a completion path that recognizes the task itself has authoritatively published the recorded epic work_branch.\n- After a successful lease-protected publish, atomically record old/new epic SHAs and reconcile a clean registered epic checkout to the published SHA, while preserving dirty, divergent-unproven, active-operation, recovery, and concurrent-update states.\n- Do not enqueue the maintenance helper as an ordinary child merge back into the epic it just rewrote; transition it through the Done-only audited maintenance lifecycle.\n- Make restart/recovery idempotently recognize an already-published exact head and resume completion without rerunning the rebase or emitting a permanent integration_retry alert.\n- Preserve branch protection, exact force-with-lease semantics, recovery reachability, auxiliary-worktree cleanup, and normal child integration behavior.\n\nRelevant code: epic staleness maintenance dispatch and completion, task submit routing, integration worktree head validation, ProjectStore registered epic worktree reconciliation, terminal transition coordination, and alert reconciliation.\n\nRequired tests:\n- Reproduce EXOCOMP-244 with a clean old registered epic checkout and a successfully force-with-lease published rebased epic; prove completion realigns safely and reaches audited Done without ordinary child integration.\n- Cover clean fast-forward publication, history-rewriting rebase with equivalent recorded range, dirty checkout, active rebase, stable recovery ref, lease loss/concurrent remote movement, missing publication evidence, restart between push and completion, repeated recovery, and ordinary child submissions.\n- Assert no unique commit or recovery ref is deleted, no reset occurs for unproven divergence, and stale integration alerts clear once exact completion is reconciled.\n- Run focused epic-rebase, maintenance, integration executor/queue, worktree recovery, terminal lifecycle, alert, and restart suites plus make test.\n\nAcceptance criteria:\n- A successful direct epic rebase cannot invalidate its own submission by construction.\n- EXOCOMP-244-style tasks converge to audited Done exactly once after the published epic is proven.\n- Unsafe or ambiguous checkout states remain preserved with actionable diagnostics.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 17:46
---
Live workaround applied safely: verified EXOCOMP-244 had no running agent; preserved old clean epic-EXOCOMP-135 head 333c3b81 under local recovery/epic-EXOCOMP-135-pre-rebase-333c3b81; detached and repointed the local epic branch to already-published 98e26f09 without reset or deletion; verified both authoritative epic and assigned task worktrees clean at 98e26f09; resubmitted from the required derived task checkout. A submit from the direct epic checkout was rejected because expected_work_branch remains epic-EXOCOMP-135--task-EXOCOMP-244, confirming the branch-model mismatch in scope.
---
author: oompah
created: 2026-08-03 17:50
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 17:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 17:51
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.4K out [1.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 8s
- Log: OOMPAH-731__20260803T175013Z.jsonl
---
author: oompah
created: 2026-08-03 17:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 17:53
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-08-03 17:53
---
Understanding: direct shared-epic rebase maintenance needs an audited Done-only completion path that proves the published epic head, safely reconciles a clean registered checkout, and preserves unsafe/concurrent/recovery states. I will trace maintenance completion, submit routing, worktree validation, and recovery, then add focused regression tests and verify the relevant suites.
---
author: oompah
created: 2026-08-03 17:55
---
Discovery: _create_workspace_for_issue currently sends all parallel shared-epic children, including auto-filed Rebase epic-* helpers, to derived private branches; submission then enqueues every parented task into ordinary child integration. That executor correctly rejects a preserved shared-epic checkout after the helper force-pushes the epic. The fix needs explicit direct-maintenance classification, canonical epic-worktree routing, guarded publication reconciliation, and audited Done staging while preserving normal child integration.
---
author: oompah
created: 2026-08-03 18:16
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 151
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 23m 13s
- Log: OOMPAH-731__20260803T175306Z.jsonl
---
author: oompah
created: 2026-08-03 18:16
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-03 18:16
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-08-03 18:33
---
Understanding (continuation): Resuming from recovery checkpoint eafabf130. Previous agent implemented: (1) is_direct_epic_maintenance_issue() classifier in integration.py, (2) reconcile_published_epic_worktree() in projects.py that safely realigns a clean registered epic checkout, (3) complete_direct_epic_maintenance_submission() in orchestrator.py that proves the published epic head and routes to audited Done without ordinary child integration, (4) submit API path that detects direct rebase helpers and bypasses the integration queue, (5) workspace routing that gives rebase helpers the canonical shared epic worktree instead of a private child branch. All 365 focused tests pass.
---
<!-- COMMENTS:END -->
