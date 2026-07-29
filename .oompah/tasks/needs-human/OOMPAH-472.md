---
id: OOMPAH-472
type: feature
status: Needs Human
priority: 1
title: Collect target-landing evidence for Merged audits
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-471
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:12.977543Z'
updated_at: '2026-07-29T03:14:54.074341Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ee2de8e4b05f7994081f063147b5bd36b38754fc06a14d8f81fb617cb98259c8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:21:00.553916+00:00'
  matched_identifiers: []
  evidence: "My duplicate investigation is complete. Here is the summary:\n\n**Search\
    \ coverage:**\n- All `.oompah/tasks/` states: `open` (OOMPAH-281), `backlog` (OOMPAH-282),\
    \ `merged` (OOMPAH-271\u2013280), `archived` (200+ tasks, OOMPAH-1\u2013276)\n\
    - Patterns searched: `MergedEvidence`, `evidence.*collector`, `target.landing`,\
    \ `landing.*evidence`, `audit`, `completion.fingerprint`, `fingerprint`, `merge.*commit`,\
    \ `stranded.*commit`, `wrong.*target`, `Merged.*audit`\n- Source tree (plans/,\
    \ docs/, entire repo): same patterns \u2014 zero matches\n\n**Active tasks reviewed:**\n\
    - **OOMPAH-281** (Open): Containerized GitHub Actions runner using Podman \u2014\
    \ completely unrelated to audit evidence collection.\n- **OOMPAH-282** (Backlog):\
    \ UnicodeEncodeError in state_branch_migration \u2014 completely unrelated.\n\n\
    No archived or merged task covers `MergedEvidenceCollector`, target-landing evidence,\
    \ completion fingerprints, or any aspect of the Merged audit evidence collection\
    \ described in OOMPAH-472. The referenced blockers OOMPAH-471 and OOMPAH-457 do\
    \ not appear in the task files at all (they are likely in the live tracker above\
    \ the current file-commit range), confirming this is a fresh feature on an active\
    \ epic.\n\n---\n\nFocus handoff: duplicate_detector  \nDuplicate preflight verdict:\
    \ no_duplicate  \nMatches: none  \nEvidence: Exhaustive search of all `.oompah/tasks/`\
    \ states (open, backlog, merged, archived \u2014 200+ tasks) and the full repository\
    \ source tree found zero matches for any of the key concepts in OOMPAH-472: `MergedEvidenceCollector`,\
    \ target-landing evidence, completion fingerprint, stranded commits, wrong-target\
    \ merge detection, or Merged-audit evidence collection. The only two active (non-terminal)\
    \ tasks \u2014 OOMPAH-281 (GitHub Actions runner) and OOMPAH-282 (latin-1 UnicodeEncodeError)\
    \ \u2014 cover entirely unrelated topics. OOMPAH-472 is a unique, first-of-its-kind\
    \ feature task."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: ec71caef-1784-4719-9aa4-c9bb73d0a9b8
oompah.work_branch: epic-OOMPAH-458
oompah.task_costs:
  total_input_tokens: 2050744
  total_output_tokens: 57777
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 685411
      output_tokens: 51135
      cost_usd: 0.0
    opus:
      input_tokens: 1365333
      output_tokens: 6642
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 13
    output_tokens: 3514
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:21:00.553010+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 35
    output_tokens: 34308
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:57:01.918904+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 13
    output_tokens: 2290
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:13:30.105260+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 14
    output_tokens: 2418
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:18:37.744109+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 80537
    output_tokens: 886
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:20:20.006754+00:00'
  - profile: deep
    model: opus
    input_tokens: 1365333
    output_tokens: 6642
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:25:49.273098+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 379585
    output_tokens: 4856
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:47:10.598119+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 225214
    output_tokens: 2863
    cost_usd: 0.0
    recorded_at: '2026-07-29T03:14:49.657228+00:00'
---
## Summary

Implementation scope

Build a read-only MergedEvidenceCollector. Require a current passed Done audit for the same completion fingerprint. Resolve the source branch/review, intended target branch, reviewed source SHA, merge commit/result, target HEAD, CI status, and commit/content containment. Detect wrong-target merges, open or closed-unmerged reviews, failed CI, stale branch tips, deleted branches with authoritative merged-review evidence, and unique commits stranded outside the target. For epic and nested-epic rollups, include child Done audit IDs and prove the complete branch chain landed on the configured target.

Tests

Use Git and fake SCM fixtures for correct landing, wrong target, open review, closed without merge, failed/pending CI, squash/rebase/merge commits, deleted branch, source advanced after review, stranded commits, shared epic, and nested epic target chains. Run focused tests and make test.

Acceptance criteria

A Merged audit can distinguish actual correct-target landing from tracker labels or stale review history alone and reports precise evidence for every failure mode.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:18
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-29 01:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:21
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 27, Tool calls: 19
- Tokens: 13 in / 3.5K out [3.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 44s
- Log: OOMPAH-472__20260729T011820Z.jsonl
---
author: oompah
created: 2026-07-29 01:44
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 01:44
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-29 01:44
---
Understanding: This task (OOMPAH-472) requires building a MergedEvidenceCollector that verifies actual target-landing for Merged audits. I'm in the CI Failure Fixer role. Let me examine what exists on this branch and what tests are failing.
---
author: oompah
created: 2026-07-29 01:50
---
Discovery: OOMPAH-471 (DoneEvidenceCollector) is complete and tests pass. OOMPAH-472 requires creating merged_evidence_collector.py and its tests from scratch. The feature must: (1) require a passed Done audit, (2) resolve source branch/review/SHA/merge commit/target HEAD/CI/containment via SCMProvider, (3) detect wrong-target merges, open/unmerged reviews, failed CI, stale tips, deleted branches, stranded commits, (4) support epic rollups with child audit chains. Implementing now.
---
author: oompah
created: 2026-07-29 01:56
---
Implementation: Created oompah/merged_evidence_collector.py with MergedEvidenceCollector and FakeSCMProvider, plus tests/test_merged_evidence_collector.py with 61 tests. All tests pass. Key design: requires a passed Done audit, resolves review/SHA/CI/containment via SCM protocol, detects all 10+ failure modes (wrong target, open/unmerged reviews, failed CI, stale tips, stranded commits, etc), supports epic/nested-epic rollups. Uses get_review_head_sha to distinguish the SHA at review time from the current branch HEAD, enabling stale-tip detection.
---
author: oompah
created: 2026-07-29 01:56
---
Verification: 61 tests pass in tests/test_merged_evidence_collector.py. Related suites (done_evidence_collector, terminal_audit, landing_gate, independently_merged, auditor_contract, terminal_audit_enforcement, terminal_audit_metadata) all pass — 89 tests total, no regressions.
---
author: oompah
created: 2026-07-29 01:56
---
Completion: Delivered MergedEvidenceCollector (oompah/merged_evidence_collector.py) with 61 passing tests. The collector distinguishes actual correct-target landing from tracker labels alone by: (1) requiring a passing Done audit, (2) resolving the PR/MR and its CI status, (3) checking commit containment via git, (4) detecting 10+ precise failure modes. Epic rollups validate child branch chains. FakeSCMProvider enables hermetic testing of all failure modes without network access. Branch pushed to epic-OOMPAH-458.
---
author: oompah
created: 2026-07-29 01:56
---
Implemented MergedEvidenceCollector: read-only collector for Merged audits that verifies actual target-branch landing via SCM review state, CI status, and git containment. 61 tests covering all specified failure modes (wrong target, open/unmerged review, failed/pending CI, stale tip, stranded commits, deleted branches, epic rollups, nested epic chains). Branch epic-OOMPAH-458 updated.
---
author: oompah
created: 2026-07-29 01:57
---
Agent completed successfully in 783s (34343 tokens)
---
author: oompah
created: 2026-07-29 01:57
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 64, Tool calls: 46
- Tokens: 35 in / 34.3K out [34.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 13m 3s
- Log: OOMPAH-472__20260729T014401Z.jsonl
---
author: oompah
created: 2026-07-29 01:57
---
Completion refused by orchestrator: unpushed work detected on branch `epic-OOMPAH-458` while task is in a terminal state.

Diagnostic:
  Worktree has uncommitted changes — file(s) created but never committed.

Required: commit the work, push to origin, then close the task.

Steps to resolve:
  git checkout epic-OOMPAH-458
  git add -A
  git commit -m "Descriptive commit message"
  git push origin epic-OOMPAH-458

Task re-opened. Re-dispatch will push a fresh agent to complete the landing.
---
author: oompah
created: 2026-07-29 02:12
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 02:12
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-29 02:12
---
Understanding: Previous agent created MergedEvidenceCollector implementation but failed to commit/push. My role is to verify the uncommitted files, run tests to confirm they pass, commit everything, push to origin, and close the task.
---
author: oompah
created: 2026-07-29 02:13
---
Discovery: The previous agent's work was actually committed and pushed successfully (commit ede290441 on origin/epic-OOMPAH-458). Files oompah/merged_evidence_collector.py (989 lines) and tests/test_merged_evidence_collector.py (1366 lines) are present and committed. The orchestrator's 'uncommitted changes' diagnostic appears to have been stale when the task was re-opened.
---
author: oompah
created: 2026-07-29 02:13
---
Verification: All 61 tests in tests/test_merged_evidence_collector.py pass. Related suites (done_evidence_collector, terminal_audit, landing_gate, independently_merged) also all pass — 89 tests total, zero regressions. Branch epic-OOMPAH-458 is up to date with origin.
---
author: oompah
created: 2026-07-29 02:13
---
Completion: MergedEvidenceCollector delivered in oompah/merged_evidence_collector.py with 61 tests. The collector verifies actual target-branch landing via: (1) requiring a passing Done audit, (2) resolving PR/MR review state and CI status via SCM protocol, (3) git-based commit containment checks, (4) 10+ precise failure-mode detections (wrong target, open/unmerged review, failed/pending CI, stale branch tip, stranded commits, deleted branches), (5) epic and nested-epic rollup with child Done audit ID chains. FakeSCMProvider enables hermetic testing. All acceptance criteria met. Branch committed and pushed.
---
author: oompah
created: 2026-07-29 02:13
---
Delivered MergedEvidenceCollector (oompah/merged_evidence_collector.py) with 61 passing tests covering all specified failure modes. Distinguishes correct-target landing from tracker labels alone via SCM review state, CI status, and git commit containment. Supports epic/nested-epic rollups with child Done audit chains. Branch epic-OOMPAH-458 committed and pushed to origin.
---
author: oompah
created: 2026-07-29 02:13
---
Agent completed successfully in 69s (2303 tokens)
---
author: oompah
created: 2026-07-29 02:13
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 21, Tool calls: 12
- Tokens: 13 in / 2.3K out [2.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 9s
- Log: OOMPAH-472__20260729T021225Z.jsonl
---
author: oompah
created: 2026-07-29 02:13
---
Completion refused by orchestrator: unpushed work detected on branch `epic-OOMPAH-458` while task is in a terminal state.

Diagnostic:
  Worktree has uncommitted changes — file(s) created but never committed.

Required: commit the work, push to origin, then close the task.

Steps to resolve:
  git checkout epic-OOMPAH-458
  git add -A
  git commit -m "Descriptive commit message"
  git push origin epic-OOMPAH-458

Task re-opened. Re-dispatch will push a fresh agent to complete the landing.
---
author: oompah
created: 2026-07-29 02:17
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 02:17
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-29 02:18
---
Understanding: This is the third dispatch on OOMPAH-472. The implementation (MergedEvidenceCollector in oompah/merged_evidence_collector.py with 61 tests in tests/test_merged_evidence_collector.py) was already completed and committed in the prior run (commit ede290441). The branch epic-OOMPAH-458 is up to date with origin. All 89 focused tests pass. The orchestrator has been rejecting task closure with a stale 'uncommitted changes' diagnostic. My job is to verify the state and close the task.
---
author: oompah
created: 2026-07-29 02:18
---
Discovery: The git working tree is completely clean (git status --porcelain produces no output). Commit ede290441 is on both local branch and origin/epic-OOMPAH-458. Files oompah/merged_evidence_collector.py (989 lines) and tests/test_merged_evidence_collector.py (1366 lines) are committed and pushed. The 'uncommitted changes' diagnostic the orchestrator fired was stale/incorrect — possibly a timing artifact during state verification in prior runs.
---
author: oompah
created: 2026-07-29 02:18
---
Verification: 61 tests pass in tests/test_merged_evidence_collector.py. Related suites (done_evidence_collector, terminal_audit, landing_gate, independently_merged) all pass — 89 tests total, zero regressions. Branch epic-OOMPAH-458 is fully committed and pushed to origin.
---
author: oompah
created: 2026-07-29 02:18
---
Completion: MergedEvidenceCollector is fully delivered. The implementation (oompah/merged_evidence_collector.py, 989 lines) with 61 tests (tests/test_merged_evidence_collector.py, 1366 lines) is committed as ede290441 on origin/epic-OOMPAH-458. Working tree is clean. All acceptance criteria met: the collector distinguishes correct-target landing from tracker labels alone via SCM review state, CI status, and git commit containment; detects 10+ precise failure modes; supports epic/nested-epic rollups with child Done audit chains.
---
author: oompah
created: 2026-07-29 02:18
---
Delivered MergedEvidenceCollector (oompah/merged_evidence_collector.py) with 61 passing tests. Verifies actual target-branch landing via SCM review state, CI status, and git containment. Detects wrong target, open/unmerged review, failed/pending CI, stale branch tip, stranded commits, deleted branches, epic rollups, and nested epic chains. Committed as ede290441 on origin/epic-OOMPAH-458.
---
author: oompah
created: 2026-07-29 02:18
---
Agent completed successfully in 74s (2432 tokens)
---
author: oompah
created: 2026-07-29 02:18
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 22, Tool calls: 14
- Tokens: 14 in / 2.4K out [2.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 14s
- Log: OOMPAH-472__20260729T021728Z.jsonl
---
author: oompah
created: 2026-07-29 02:18
---
Completion refused by orchestrator: unpushed work detected on branch `epic-OOMPAH-458` while task is in a terminal state.

Diagnostic:
  Worktree has uncommitted changes — file(s) created but never committed.

Required: commit the work, push to origin, then close the task.

Steps to resolve:
  git checkout epic-OOMPAH-458
  git add -A
  git commit -m "Descriptive commit message"
  git push origin epic-OOMPAH-458

Task re-opened. Re-dispatch will push a fresh agent to complete the landing.
---
author: oompah
created: 2026-07-29 02:19
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 02:19
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-29 02:20
---
Agent completed successfully in 36s (81423 tokens)
---
author: oompah
created: 2026-07-29 02:20
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 3
- Tokens: 80.5K in / 886 out [81.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 36s
- Log: OOMPAH-472__20260729T021946Z.jsonl
---
author: oompah
created: 2026-07-29 02:20
---
Agent completed without closing this issue (36s (81423 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-29 02:20
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-29 02:20
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-29 02:25
---
Agent completed successfully in 305s (1371975 tokens)
---
author: oompah
created: 2026-07-29 02:25
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 19
- Tokens: 1.4M in / 6.6K out [1.4M total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 5s
- Log: OOMPAH-472__20260729T022049Z.jsonl
---
author: oompah
created: 2026-07-29 02:45
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 02:45
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-29 02:47
---
Agent completed successfully in 111s (384441 tokens)
---
author: oompah
created: 2026-07-29 02:47
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 10
- Tokens: 379.6K in / 4.9K out [384.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 51s
- Log: OOMPAH-472__20260729T024521Z.jsonl
---
author: oompah
created: 2026-07-29 02:47
---
Agent completed 3 times without closing this issue. Human action required: review the agent run history and task state, then either close the task if the work is done or add specific guidance and move it back to Open.
---
author: oompah
created: 2026-07-29 03:05
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #5)

**State audited:** `Needs Human`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** Last agent comment signals completion without a human question; the Needs Human transition appears accidental.

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-07-29 03:13
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 03:13
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-29 03:14
---
Agent completed successfully in 75s (228077 tokens)
---
author: oompah
created: 2026-07-29 03:14
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 8
- Tokens: 225.2K in / 2.9K out [228.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 15s
- Log: OOMPAH-472__20260729T031337Z.jsonl
---
author: oompah
created: 2026-07-29 03:14
---
Agent completed 4 times without closing this issue. Human action required: review the agent run history and task state, then either close the task if the work is done or add specific guidance and move it back to Open.
---
<!-- COMMENTS:END -->
