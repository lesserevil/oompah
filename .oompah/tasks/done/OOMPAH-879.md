---
id: OOMPAH-879
type: task
status: Done
priority: null
title: Prevent concurrent duplicate epic-rebase tasks for one epic generation
parent: OOMPAH-763
children:
- OOMPAH-891
- OOMPAH-892
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T10:40:35.699435Z'
updated_at: '2026-08-07T17:28:18.139252Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-879
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4b9ec0bb21e4c1d3a984ccccb80a5a09a30fe3b98a5295807976e833d679c42d
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-07T11:33:20.542522+00:00'
  matched_identifiers: []
  evidence: Owner review confirms OOMPAH-879 is the unique systemic atomicity fix
    for concurrent duplicate epic-rebase task creation. OOMPAH-853 repairs corpus
    visibility but does not implement this per-epic-generation scheduling authority.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-07T11:33:20.542522+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: Owner review confirms OOMPAH-879 is the unique systemic
    atomicity fix for concurrent duplicate epic-rebase task creation. OOMPAH-853 repairs
    corpus visibility but does not implement this per-epic-generation scheduling authority.
oompah.agent_run_id: 8601033e-1631-489a-a84b-303631ab28c6
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-879
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-879
  base_branch: epic-OOMPAH-763
  base_sha: 04fa6781091efc6f11b952b9f1b35123facce64f
  updated_at: '2026-08-07T10:44:34.962991+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1854
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1854
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1854
    cost_usd: 0.0
    recorded_at: '2026-08-07T10:47:59.279039+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-879__20260807T104455Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-879
    source_sha: 04fa6781091efc6f11b952b9f1b35123facce64f
    completed_at: '2026-08-07T10:47:59.311802+00:00'
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-9a9c6baee4bc
    project_id: proj-14849f1b
    task_id: OOMPAH-879
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cf8a16c39a5688538aa4b6f340de396079a89f57d6d8838c9c4c1039a813dfd4
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct-owner implementation received independent security review, passed
      the exact combined full gate at a85a36baf, and was published by an exact remote
      lease; no independent auditor can run safely on the paused pre-fix service.
    created_at: '2026-08-07T17:28:12.603051+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Live reproduction 2026-08-07: OOMPAH-877 already represented the required epic-OOMPAH-763 rebase and was under an active direct-owner claim while waiting for Ready child heads OOMPAH-854@91e76723e and OOMPAH-866@f959c1827 to integrate. The stale-epic scheduler nevertheless auto-filed and dispatched duplicate OOMPAH-878 against the same epic generation and clean shared epic worktree at 04fa678, which would have published an obsolete rebase before those children landed. Implementation scope: make rebase filing/dispatch an atomic per-project+epic+target-generation decision; treat every nonterminal rebase task, active owner claim, running generation, and durable rebase job as mutually exclusive authority; re-evaluate prerequisites and epic head immediately before worker admission and before push; archive/supersede duplicate auto-filed tasks without provider work. Relevant code: epic staleness/rebase filing, duplicate preflight qualification, direct-owner admission, durable workflow jobs, and shared epic worktree fencing. Required tests: a claimed existing rebase prevents a second filing and dispatch; concurrent staleness ticks yield one task; a newly integrated child invalidates an older rebase generation before push; restart preserves exclusivity; a genuinely new main/epic generation can file exactly one successor after prior terminal completion. Acceptance: at most one actionable rebase authority exists per epic generation, and no stale duplicate can mutate or publish the epic branch.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 10:44
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 10:44
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 10:47
---
Live stale-generation reproduction during OOMPAH-877 sequencing (2026-08-07): the first prematurely dispatched direct epic-rebase helper captured integration.base_sha=04fa6781091efc6f11b952b9f1b35123facce64f. OOMPAH-854, OOMPAH-866, and possibly OOMPAH-846 will integrate into epic-OOMPAH-763 before the operator-owned rebase starts. The task CLI submit path sends no base_sha and _submission_record prefers the existing value, so an otherwise correct later submission would retain 04fa678 and omit newly integrated child ranges from the direct-rebase generation. The operator will work around this in flight by using the authenticated standard submit endpoint with explicit base_sha equal to the exact pre-rebase origin/epic-OOMPAH-763 head and CLI-equivalent clean/remote/branch/head evidence. Acceptance should cover refreshing/superseding an older helper generation after new child integration, while preserving the older value as forensic evidence until authoritative publication.
---
author: oompah
created: 2026-08-07 10:48
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 34s
- Log: OOMPAH-879__20260807T104455Z.jsonl
---
author: oompah
created: 2026-08-07 10:48
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-847, OOMPAH-848, OOMPAH-849, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861, OOMPAH-862, OOMPAH-863, OOMPAH-864, OOMPAH-865, OOMPAH-866, OOMPAH-877, OOMPAH-878. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
author: oompah
created: 2026-08-07 11:27
---
Live recurrence #3: OOMPAH-880 was auto-filed/dispatched while direct-owner claims already fenced OOMPAH-877 and OOMPAH-878 for the same epic generation. It began a shared-worktree rebase and reached detached HEAD 063853c with unresolved index conflicts before owner takeover retired it. Remote remained 04fa; recovery refs/archive were preserved and the checkout restored. Acceptance coverage must include existing claimed rebase tasks plus scheduler ticks that create another task before prerequisite integration, and must guarantee no shared-worktree mutation by the loser.
---
author: oompah
created: 2026-08-07 11:55
---
Live recurrence #4 while this fix is in progress: OOMPAH-881 auto-filed and launched a Claude/sonnet provider despite active direct claims on O877/O878/O880 and the same unchanged epic generation 04fa678. Owner takeover stopped it before shared-worktree mutation. Regression must cover repeated scheduler ticks continuing to mint new rebase task identifiers while earlier generation authorities are owner-fenced; task-ID uniqueness is not generation uniqueness.
---
author: oompah
created: 2026-08-07 11:55
---
Additional live reproduction on 2026-08-07: OOMPAH-881 was auto-filed and dispatched for the same epic-OOMPAH-763 stale generation while OOMPAH-877, OOMPAH-878, and OOMPAH-880 already had active direct-owner claims. O881 reached a live Claude/sonnet provider (run c07d6c38901e49a58b9b9d1a4e5c7443) and announced it was about to run rebase. An authenticated direct-owner claim 0d873a86e39a4b7087e3374f3286f163 retired it before mutation; shared epic stayed clean at 04fa6781091efc6f11b952b9f1b35123facce64f. Acceptance must fence duplicate auto-file and dispatch across active direct-owner claims for every existing duplicate, not merely running rows.
---
author: oompah
created: 2026-08-07 12:04
---
Fifth live duplicate reproduction: OOMPAH-882 auto-filed/dispatched between OOMPAH-877 clean preflight and its authorized rebase command, despite active direct-owner claims on O877/O878/O880/O881. O882 began the exact 04fa678 to c9f16e3 rebase and stopped step 9/78 before operator containment. Claim 6344dd46defe4c9ba2ac75d3a90761e3 retired it; recovery refs/archive and exact SHA evidence are recorded on O882. Acceptance must make duplicate-generation filing plus dispatch atomic with existing task/owner claims; a preflight-only fence is demonstrably insufficient.
---
author: oompah
created: 2026-08-07 12:38
---
Live recurrence #6: OOMPAH-884 was auto-filed and dispatched while OOMPAH-877 plus four duplicate helpers were already fenced. It observed the operator's newly rebased local shared worktree and force-pushed unvalidated ca1c52744 to origin/epic-OOMPAH-763 at 12:30 UTC, before the focused semantic suite later reported three failures. The operator claimed OOMPAH-884 after tracing its agent log. Acceptance must cover a duplicate helper discovering another authority's completed local mutation and forbid its push, including generic force-with-lease syntax that lacks the exact recorded ref/SHA CAS.
---
author: oompah
created: 2026-08-07 12:43
---
Live recurrence #7: OOMPAH-885 was auto-filed in Needs Rebase after duplicate O884 had already published ca1 and been owner-fenced, while authorized O877 was locally repairing the same shared epic against newer main. Operator acquired a direct-owner claim before dispatch. This confirms task-state changes and a newly stale target can keep minting helpers while an existing rebase authority remains live; generation authority must survive target-head churn and supersede/fence new helper identifiers before provider launch.
---
author: oompah
created: 2026-08-07 13:17
---
Live recurrence #8: scheduler created OOMPAH-888 (Needs Rebase) for epic-OOMPAH-763 while OOMPAH-877 remained the sole active helper and its repaired 911-test semantic union had just passed. Operator acquired direct-owner claim 4963baca22fc4853ba6e8ee89b382446 before implementation. Add OOMPAH-888 to the durable one-authority regression corpus; it must not be admitted or allowed to push.
---
author: oompah
created: 2026-08-07 13:31
---
Recurrence #9 observed as OOMPAH-890 while canonical OOMPAH-877 full gate was still running. Root fenced OOMPAH-890 with a direct-owner claim before implementation. Add explicit OOMPAH-890 coverage alongside OOMPAH-888: a stable unresolved generation must not create or dispatch another helper after one is reserved/owned.
---
author: oompah
created: 2026-08-07 13:41
---
Recurrence #10 observed as OOMPAH-893 after canonical OOMPAH-877 full gate completed with four failures and before any publish. Root fenced it before implementation. Extend recurrence coverage through OOMPAH-893: one unresolved authority generation must have exactly one durable helper despite validation delay/failure.
---
author: oompah
created: 2026-08-07 13:54
---
Recurrence #11 observed as OOMPAH-895 after canonical OOMPAH-877 final full gate began. Root applied direct-owner takeover immediately. Extend generation regression through O895, including the case where a duplicate reaches scheduler claim/In Progress before the canonical helper publishes.
---
author: oompah
created: 2026-08-07 14:08
---
Recurrence #12 / decisive capability evidence: OOMPAH-896 launched after service restart, native Codex subscription (, network_access_enabled=true), and ran  at 14:05, moving remote ca1c52744 -> a70fe0bc9 while canonical O877 full gate was only ~51%. Root fenced O896 after submission. O891 must exclude this backend and sandbox all worker command paths; O892 must be the sole server-owned exact-CAS publisher after gate/authority revalidation.
---
author: oompah
created: 2026-08-07 14:17
---
Recurrence evidence from OOMPAH-897: after a corrective exact-CAS rollback left remote epic-OOMPAH-763 at ca1c527, a second scheduler worker launched, entered the same shared worktree, rebased it, and attempted its own validation while OOMPAH-877 owned acceptance work. Supported owner takeover retired PID 2476147 and descendants; remote stayed fenced. This directly validates the need for OOMPAH-891 credential/workspace isolation and OOMPAH-892 server-owned CAS publication. Recovery refs protect 78e93d/a70fe0/d008. Project remains paused.
---
author: oompah
created: 2026-08-07 17:01
---
Combined shared epic head 02eb534fa completed the first exact full make test gate: 17,367 passed, 7 skipped, 1 xfailed, with 14 failures isolated to four compatibility-contract clusters (auditor read-only Git policy, rebase admission fixtures, detached-descendant validation fencing, and legacy terminal-audit recovery). Independent repairs are running in parallel; project remains paused pending a green exact-head rerun.
---
author: oompah
created: 2026-08-07 17:28
---
Final combined shared-epic head a85a36baf7b3ebcb45be27823755b5694a790a49 passed the exact full gate: terminal mutation scan 9/9 and make test 17,381 passed, 7 skipped, 1 expected xfail, 0 failed in 1207.74s. The head was published to origin/epic-OOMPAH-763 using exact force-with-lease against prior remote e06bec5490b9d55d169f7de439755c49eff35307 and the remote now resolves exactly to a85a36baf. O891/O892 reviewed safeguards and O846/O854 lifecycle protections are included.
---
<!-- COMMENTS:END -->
