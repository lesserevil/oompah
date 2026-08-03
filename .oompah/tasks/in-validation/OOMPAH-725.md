---
id: OOMPAH-725
type: task
status: In Validation
priority: null
title: Reject lifecycle-incompatible Merged overrides for shared-epic children
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T15:33:53.224136Z'
updated_at: '2026-08-03T16:58:41.144198Z'
work_branch: OOMPAH-725
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/683
review_number: '683'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ad31e0ee18386818195c444dd324348912d9da0616165babeecbcfae7117da8d
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T15:59:47.671629+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Closest reviewed tasks were OOMPAH-165 (epic landing\
    \ detection), OOMPAH-162 (stacked child landing), and OOMPAH-168 (shared workflow\
    \ simplification); all are terminal and address different behavior.\nFocus handoff:\
    \ duplicate_detector  \nDuplicate preflight verdict: no_duplicate  \nMatches:\
    \ none  \n\nEvidence: Closest reviewed tasks were OOMPAH-165 (epic landing detection),\
    \ OOMPAH-162 (stacked child landing), and OOMPAH-168 (shared workflow simplification);\
    \ all are terminal and address different behavior."
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
oompah.task_costs:
  total_input_tokens: 50391
  total_output_tokens: 395
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 50391
      output_tokens: 395
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 50391
    output_tokens: 395
    cost_usd: 0.0
    recorded_at: '2026-08-03T15:59:47.668765+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-725__20260803T155925Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-725
    source_sha: d510748342777dd4748070d83391ffb0eae40091
    completed_at: '2026-08-03T15:59:47.680961+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-725
  head_sha: 34be8724a511307bd44ccb9d58f7c8101494aaf0
  submitted_at: '2026-08-03T16:40:45.536208+00:00'
  updated_at: '2026-08-03T16:40:45.536208+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/683
oompah.review_number: '683'
oompah.work_branch: OOMPAH-725
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-8bd41fcb5696
    project_id: proj-14849f1b
    task_id: OOMPAH-725
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a7ff1bb74939f78604a194da24ce954526fe1fe19b662ff3f25fbee78b54e14f
    attempts:
    - version: 1
      attempt_id: attempt-4197d293cfc6
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a7ff1bb74939f78604a194da24ce954526fe1fe19b662ff3f25fbee78b54e14f
      created_at: '2026-08-03T16:58:32.455068+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T16:58:32.455068+00:00'
      branch_key: OOMPAH-725
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T16:57:49.580019+00:00'
    updated_at: '2026-08-03T16:58:32.455068+00:00'
  - version: 1
    audit_id: audit-7739be5a5fd4
    project_id: proj-14849f1b
    task_id: OOMPAH-725
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a7ff1bb74939f78604a194da24ce954526fe1fe19b662ff3f25fbee78b54e14f
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T16:57:49.580019+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-4197d293cfc6
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a7ff1bb74939f78604a194da24ce954526fe1fe19b662ff3f25fbee78b54e14f
    created_at: '2026-08-03T16:58:32.455068+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T16:58:32.455068+00:00'
    branch_key: OOMPAH-725
---
## Summary

Live reproduction: EXOCOMP-240 is an auto-filed rebase maintenance task parented by shared epic EXOCOMP-130. Its completion auditor passed the required Done transition. A later project-owner terminal override changed the child to Merged even though its work landed only on epic-EXOCOMP-130, not the project default branch. The epic rollup correctly rejects that evidence and now logs EXOCOMP-240=Merged (requires Done), so a superficially more terminal state indefinitely blocks the parent.

Implementation scope:
- Enforce shared-epic child lifecycle compatibility at every terminal transition boundary, including project-owner audit override, ACP override, API/CLI set-status, recovery, and maintenance/rebase completion.
- A child whose accepted work is contained only in its parent epic branch may reach audited Done but may not reach Merged until the parent review lands on the configured target branch.
- Auto-filed epic rebase/maintenance tasks must use Done as their successful terminal target and must not enqueue or invite a second Merged transition merely because they mutate the epic branch directly.
- Preserve legitimate owner override authority for evidence-backed emergency recovery, but reject structurally impossible Merged evidence with a precise conflict explaining the required parent landing.
- Add reconciliation for existing incompatible Merged children: when Done audit evidence exists and the parent has not landed, safely restore Done without rerunning implementation or losing audit history.

Relevant code: terminal_transition_coordinator owner overrides, API/ACP terminal boundaries, shared-epic strategy validation, auto-filed rebase completion, epic rollup reconciliation, and terminal-audit enforcement recovery.

Required tests:
- Reproduce EXOCOMP-240: maintenance child passes Done, owner requests Merged before parent landing, request is rejected and parent completion still accepts the child as Done.
- Cover ordinary shared-epic children, nested epics, default-branch landing followed by legitimate Merged, API and ACP owner overrides, restart recovery, and legacy incompatible records.
- Prove the repair preserves the completed Done audit and cancels no unrelated audit.
- Run focused terminal-override, transition-coordinator, epic-strategy, maintenance/rebase, lifecycle, and terminal-audit-enforcement suites plus make test.

Acceptance criteria:
- A shared-epic child cannot enter Merged solely because its commit is on the epic branch.
- Existing EXOCOMP-240-style records converge to audited Done and no longer block rollup.
- Legitimately target-landed children and top-level tasks can still reach Merged through normal audited or owner-override paths.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 15:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 15:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 15:59
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.4K in / 395 out [50.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 33s
- Log: OOMPAH-725__20260803T155925Z.jsonl
---
author: oompah
created: 2026-08-03 16:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 16:02
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-03 16:03
---
Understanding: shared-epic children must be blocked from Merged until accepted work reaches the configured target branch; maintenance/rebase children should terminate at audited Done. I will trace the shared-epic strategy, terminal transition coordinator, API/ACP and recovery paths, then centralize compatibility validation, add legacy reconciliation, and cover the requested lifecycle/override cases with focused tests.
---
author: oompah
created: 2026-08-03 16:06
---
Discovery: terminal writes are already funneled through TerminalTransitionCoordinator, but its request/apply/override paths lack shared-epic lifecycle context, allowing owner overrides to bypass rollup checks. Orchestrator already provides authoritative parent-review landing detection via _epic_branch_landed_on_target and identifies auto-filed rebase helpers. I will reuse that through a coordinator/enforcement callback and repair incompatible legacy Merged records before restart recovery can replay them.
---
author: oompah
created: 2026-08-03 16:38
---
Implementation: Wired lifecycle validation into both production terminal coordinators, request/retry/apply/override paths, and enforcement recovery. Shared-epic children now require parent review landing evidence for Merged; auto-filed rebase/maintenance children remain Done. Added legacy reconciliation to restore incompatible Merged children to completed Done while preserving audit history and unrelated audits, with API/ACP conflict propagation and scanner allowlist coverage.
---
author: oompah
created: 2026-08-03 16:39
---
Verification: Focused terminal coordinator, terminal-audit enforcement, API/ACP status interfaces, epic strategy/rebase, lifecycle, and terminal-audit contract suites passed (389 passed, 1 expected xfail; follow-up boundary checks 233 passed). The terminal mutation scan passes (7/7 allowlisted). make[1]: Entering directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-725'
make[1]: Leaving directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-725' was attempted twice but could not bootstrap its managed uv environment because astral-uv.uv failed with DBus InvalidArgs (kernel-thread transient scope error), before tests started.
---
author: oompah
created: 2026-08-03 16:39
---
Verification: Focused terminal coordinator, terminal-audit enforcement, API/ACP status interfaces, epic strategy/rebase, lifecycle, and terminal-audit contract suites passed (389 passed, 1 expected xfail; follow-up boundary checks 233 passed). The terminal mutation scan passes (7/7 allowlisted). make test was attempted twice but could not bootstrap its managed uv environment because astral-uv.uv failed with DBus InvalidArgs (kernel-thread transient scope error), before tests started.
---
author: oompah
created: 2026-08-03 16:40
---
Completion: Delivered shared-epic lifecycle enforcement, Done-only maintenance/rebase completion, API/ACP conflict propagation, serialized recovery safeguards, and legacy Merged-to-Done reconciliation with focused regression coverage. The branch is ready for commit and push; the only unresolved verification item is the environment-level make test bootstrap failure documented above.
---
author: oompah
created: 2026-08-03 16:40
---
Shared-epic Merged lifecycle enforcement, Done-only maintenance completion, and legacy reconciliation delivered; focused suites and terminal mutation scan pass. make test bootstrap remains environment-blocked by astral-uv DBus failure.
---
author: oompah
created: 2026-08-03 16:40
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 193
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 38m 22s
- Log: OOMPAH-725__20260803T160238Z.jsonl
---
author: oompah
created: 2026-08-03 16:48
---
Branch quality gate passed for `34be8724a511307bd44ccb9d58f7c8101494aaf0` using `make test` in 414.6s. Review creation may proceed.
---
author: oompah
created: 2026-08-03 16:57
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-03 16:57
---
YOLO: merged PR #683.
---
author: oompah
created: 2026-08-03 16:58
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 16:58
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
