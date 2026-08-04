---
id: OOMPAH-749
type: bug
status: In Progress
priority: 0
title: Bound historical audit replay so Ready integration claims cannot starve
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T00:41:30.892995Z'
updated_at: '2026-08-04T03:32:26.844891Z'
work_branch: OOMPAH-749
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/703
review_number: '703'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4698d2271ba63ef638c73fc19cc3cefef395888bec37a945df02b8759054e000
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T00:43:59.049551+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: Examined all 33 similarity candidates in the provided corpus. OOMPAH-749
    describes a specific starvation bug in the integration queue audit replay system
    where historical audits block live Ready submissions. The closest thematic match
    is OOMPAH-172 epic (archived) which implements release-delivery queuing and recovery
    patterns, but that addresses a different orchestrator subsystem (release branches,
    not integration audits). No active task in the corpus describes the same root
    cause (unbounded historical audit replay starving Ready row claims). The required_peer_count
    is 0 and omitted_peer_count is 0, confirming no structural peer requirement was
    omitted.

    Looking at OOMPAH-749, I need to determine whether it''s a duplicate of an existing
    task by examining the supplied corpus.


    **OOMPAH-749 Issue Analysis:**

    - **Title:** "Bound historical audit replay so Ready integration claims cannot
    starve"

    - **Problem:** Integration driver processes entire historical audit set before
    claiming live Ready rows, causing starvation

    - **Scope:** _process_integration_queues, IntegrationQueue ledger scans, integration
    audit staging, lease claiming

    - **Domain:** Integration queue processing, audit recovery, cross-project fairness

    - **Status:** Open (active)


    **Corpus Search:**


    I''ve reviewed all 33 similarity candidates provided (plus noting that 423 were
    omitted from 456 total). Here are the closest matches examined:


    - **OOMPAH-172 through OOMPAH-202** (Archived): Release-branch addendums, release
    delivery queues, cherry-pick operations, ledger migration. These involve queue
    claiming and recovery patterns but are specific to **release delivery**, not **integration
    audit replay**.

    - **OOMPAH-187** (Archived): Dashboard filtering for in-flight tasks. Unrelated.

    - **OOMPAH-205** (Archived): Board reconciliation performance. Unrelated.

    - **OOMPAH-177, OOMPAH-195** (Archived): Release-addendum queue and executor.
    Different domain (release branches vs. integration audits).

    - All others (Archived): Epic workflows, issue templates, tracker sync, etc. No
    overlap.


    **Key Distinctions:**

    - OOMPAH-749 addresses **integration queue audit replay** blocking live Ready
    submissions

    - The closest archived tasks (OOMPAH-172+) address **release delivery queue**
    claiming

    - These are distinct subsystems with similar patterns but different responsibilities

    - All candidates in corpus are terminal (Archived), not active duplicates


    **Verdict:**


    Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none


    Evidence: Examined all 33 similarity candidates in the provided corpus. OOMPAH-749
    describes a specific starvation bug in the int'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: f37b7591-ad0f-4b51-8f58-04c97793e447
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2521
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2521
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2521
    cost_usd: 0.0
    recorded_at: '2026-08-04T00:43:58.453230+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-749__20260804T004313Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-749
    source_sha: 4ea94b151a09758c57a93c8710c05f28a49bcc2a
    completed_at: '2026-08-04T00:43:58.458602+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-749
  head_sha: 713f7908041162620b6a2c587d2aac1c14bc3104
  submitted_at: '2026-08-04T01:00:46.555314+00:00'
  updated_at: '2026-08-04T01:00:46.555314+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/703
oompah.review_number: '703'
oompah.work_branch: OOMPAH-749
oompah.target_branch: main
---
## Summary

Live reproduction on 2026-08-04: the integration ledger contains 37 Ready submissions across Oompah, Exocomp, and Nodevirt, with the oldest submitted 2026-08-01. Every row still has attempts=0, no lease owner, and no last error after repeated healthy ticks and a service restart. The integration driver scans and stages audits for the entire historical integrated set before it groups and claims live Ready rows, so growing history can indefinitely postpone forward work while the main orchestrator remains healthy. Implementation scope: make historical integrated-audit recovery incremental and bounded by a durable cursor or batch budget; claim or fairly interleave live Ready work before replaying unbounded history; preserve idempotent audit staging, lease recovery, per-epic serialization, dependencies, and cross-project fairness; expose progress and a degraded signal when Ready rows receive no claim within the expected interval. Relevant code includes _process_integration_queues, integrated terminal-audit staging, IntegrationQueue ledger scans, scheduling futures, and state metrics. Required tests: hundreds of historical integrated rows plus a live Ready row claimed within one driver interval; bounded replay across restarts; fair progress across projects and epic groups; dependency-blocked rows skipped without blocking eligible groups; no duplicate audits or lost lease recovery. Acceptance criteria: queue latency is bounded independently of historical ledger size, existing 37 Ready rows begin receiving leases naturally, and stalled claim progress becomes observable rather than silently healthy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 00:43
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 00:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 00:44
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.5K out [2.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 59s
- Log: OOMPAH-749__20260804T004313Z.jsonl
---
author: oompah
created: 2026-08-04 00:45
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 00:45
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-08-04 00:46
---
Understanding: bound integrated terminal-audit replay so historical ledger growth cannot delay Ready claims. I will trace _process_integration_queues and ledger scans, add the smallest durable/bounded scheduling change with regression coverage, verify focused integration tests, then commit, push, and submit.
---
author: oompah
created: 2026-08-04 00:46
---
Discovery: _process_integration_queues materializes every queue row, then awaits _stage_integrated_task_audit for every integrated row before grouping/claiming Ready work. IntegrationQueue.items has no bounded/cursor scan, so replay is unbounded and repeats after restart. I am checking config and maintenance-status conventions for a durable cursor plus observable incomplete/stalled progress.
---
author: oompah
created: 2026-08-04 00:52
---
Implementation: added state-filtered/keyset queue scans with opaque cursors; added configurable integration audit batch and Ready-claim timeout; moved integrated audit replay after live Ready/integrating groups; persisted cursor after each audit staging; added integration queue progress metrics and an idempotent degraded alert for overdue eligible Ready rows. Next I am adding regression coverage for restart/cursor bounds, live claim precedence, and dependency-blocked rows.
---
author: oompah
created: 2026-08-04 00:56
---
Verification update: focused new regressions pass, including 200 historical integrated rows with live Ready claim first, bounded replay cursor resumption across restart, and degraded signaling that ignores dependency-blocked Ready rows. Running directly affected parallel-epic, standalone Ready, queue, and config suites next.
---
author: oompah
created: 2026-08-04 01:00
---
Verification: 171 affected tests pass across delivery recovery, parallel epic integration, queue storage, and configuration suites. The 200-history regression confirms the live Ready row is claimed before audit replay; cursor replay resumes after restart; dependency-blocked rows do not trigger false degraded claims. compileall and git diff --check also pass.
---
author: oompah
created: 2026-08-04 01:00
---
Completion: delivered and pushed commit 713f79080. Historical integrated-audit recovery is now cursor-based and batch-bounded, live Ready claims run first with dependency/lease behavior preserved, and integration queue progress exposes cursor/batch/Ready-age metrics plus a degraded alert for overdue eligible rows. Focused verification passed (171 affected tests plus the 200-history regression); branch is clean and up to date with origin.
---
author: oompah
created: 2026-08-04 01:01
---
Bound historical integrated-audit replay with durable cursor and batch budget; prioritize live Ready claims and expose stalled progress.
---
author: oompah
created: 2026-08-04 01:01
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 86
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 15m 37s
- Log: OOMPAH-749__20260804T004550Z.jsonl
---
author: oompah
created: 2026-08-04 03:03
---
Live re-examination at 2026-08-04 03:02 UTC: all 37 shared integration-queue rows across Oompah, Nodevirt, and Exocomp still have attempts=0 and no lease under live revision 11d81c27. OOMPAH-749 head 713f79080 is now in the active quality gate. The live OOMPAH-752 fairness fix selected this repair after OOMPAH-735's gate, so the root remediation is progressing. No task-local queue mutation is safe or necessary while this exact fix is flowing.
---
author: oompah
created: 2026-08-04 03:07
---
Branch quality gate passed for `713f7908041162620b6a2c587d2aac1c14bc3104` using `make test` in 430.9s. Review creation may proceed.
---
author: oompah
created: 2026-08-04 03:21
---
YOLO: Merge conflict detected on MR #703. Rebase onto main and resolve conflicts.
---
author: oompah
created: 2026-08-04 03:22
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-04 03:22
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-08-04 03:24
---
Understanding: This branch has 1 commit (713f79080) for bounded integrated audit replay. Rebasing onto origin/main which has advanced with commits from OOMPAH-731, 734, 735, 747, 750, 751, 752 – many overlap files (orchestrator.py etc). Starting rebase now.
---
<!-- COMMENTS:END -->
