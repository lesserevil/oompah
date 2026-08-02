---
id: OOMPAH-705
type: bug
status: In Validation
priority: 1
title: Fetch an accepted submission head before standalone review gating
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T21:30:29.609691Z'
updated_at: '2026-08-02T23:58:02.233490Z'
work_branch: OOMPAH-705
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/666
review_number: '666'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9022b41abb779a660b1286993c3e62e509999d8ccc4856fcec48a9ffbcd1a4a8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-02T21:52:06.494796+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\n\nEvidence: I reviewed the current project task corpus for active\
    \ (non-terminal) peer tasks that could describe the same underlying problem \u2014\
    \ a review-gating regression in `_review_quality_gate_passes` / `_quality_gate_branch_head`\
    \ where the managed clone at `project.repo_path` lacks the freshly-pushed submitted\
    \ head SHA (e.g., `5640fc49e3036e552d4c047c9c35b6509e94e8cd` for OOMPAH-704) and\
    \ reports `Head: unknown` / `infrastructure_error` without running CI. OOMPAH-705\
    \ explicitly references OOMPAH-700 as the original submission-promise task and\
    \ OOMPAH-704 as the reproduction trigger; the description asks to fetch/materialize\
    \ the persisted submitted head into the managed repo before gating.\n\nThe supplied\
    \ corpus lists no other tasks referencing `_review_quality_gate_passes`, `_quality_gate_branch_head`,\
    \ `integration.head_sha`, `refs/remotes/origin/OOMPAH-704`, or the non-canonical\
    \ submission head-fetch problem. The nearest previously reviewed tasks all address\
    \ orthogonal concerns: OOMPAH-10 (native markdown tracker `git pull --rebase`\
    \ sync failures), OOMPAH-162/OOMPAH-165 (stacked/shared epic landed detection\
    \ at merge time), OOMPAH-163 (target-branch allowlist for epic branches), OOMPAH-172/OOMPAH-175\
    \ (release-branch catalog discovery via `git ls-remote`) \u2014 none of them touch\
    \ the review-gate head-materialization path or the specific stale managed-clone\
    \ / submitted-head-SHA binding that OOMPAH-705 requires. The referenced upstream\
    \ tasks OOMPAH-700 and OOMPAH-704 are not present in the supplied corpus slice\
    \ as active peers. No active duplicate identified."
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
  total_input_tokens: 23
  total_output_tokens: 881
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 6
      output_tokens: 664
      cost_usd: 0.0
    unknown:
      input_tokens: 17
      output_tokens: 217
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 6
    output_tokens: 664
    cost_usd: 0.0
    recorded_at: '2026-08-02T21:52:05.568737+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 17
    output_tokens: 217
    cost_usd: 0.0
    recorded_at: '2026-08-02T23:57:53.492330+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-705__20260802T215147Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: opus
    focus: duplicate_detector
    source_branch: OOMPAH-705
    source_sha: 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd
    completed_at: '2026-08-02T21:52:05.571231+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-705
  head_sha: 73e20b64c99a542bbbab3c84237af916193b1a7c
  submitted_at: '2026-08-02T22:15:43.215768+00:00'
  updated_at: '2026-08-02T22:15:43.215768+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/666
oompah.review_number: '666'
oompah.work_branch: OOMPAH-705
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-5afe11e5d803
    project_id: proj-14849f1b
    task_id: OOMPAH-705
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6eee60cd233a1743770b04898cd0283aa5702df57db747cecd99cd19db4a192e
    attempts:
    - version: 1
      attempt_id: attempt-c5697155a051
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 6eee60cd233a1743770b04898cd0283aa5702df57db747cecd99cd19db4a192e
      created_at: '2026-08-02T23:57:03.764979+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-02T23:57:03.764979+00:00'
      branch_key: OOMPAH-705
      failure_classification: infrastructure_error
      ended_at: '2026-08-02T23:57:56.472545+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy denied a mutating or compound shell command; auditors
        cannot edit, commit, push, merge, or change state'
      next_retry_at: '2026-08-02T23:58:06.472514+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T23:55:45.912080+00:00'
    updated_at: '2026-08-02T23:57:56.472545+00:00'
  - version: 1
    audit_id: audit-01a9cb534a45
    project_id: proj-14849f1b
    task_id: OOMPAH-705
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6eee60cd233a1743770b04898cd0283aa5702df57db747cecd99cd19db4a192e
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T23:55:45.912080+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-c5697155a051
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6eee60cd233a1743770b04898cd0283aa5702df57db747cecd99cd19db4a192e
    created_at: '2026-08-02T23:57:03.764979+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-02T23:57:03.764979+00:00'
    branch_key: OOMPAH-705
    failure_classification: infrastructure_error
    ended_at: '2026-08-02T23:57:56.472545+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy denied a mutating or compound shell command; auditors
      cannot edit, commit, push, merge, or change state'
    next_retry_at: '2026-08-02T23:58:06.472514+00:00'
---
## Summary

Triggered by: OOMPAH-704

Production regression of OOMPAH-700: OOMPAH-704 was submitted from a clean non-canonical worktree with branch OOMPAH-704 and exact head 5640fc49e3036e552d4c047c9c35b6509e94e8cd. The API accepted and persisted integration.task_branch and integration.head_sha, and origin/OOMPAH-704 existed at that SHA, but _review_quality_gate_passes called _quality_gate_branch_head against project.repo_path (/home/shedwards/.oompah/repos/oompah) before fetching the newly pushed ref. Because that managed clone lacked refs/remotes/origin/OOMPAH-704, review gating reported Head: unknown and infrastructure_error without running CI. Implementation scope: bind the gate to the persisted submitted head SHA; fetch/materialize that exact object/ref into the managed repository when absent, with bounded authenticated git operations and clear infrastructure errors; verify the fetched branch tip still equals integration.head_sha before running; preserve branch-advancement fencing and never silently substitute a newer remote head. Avoid requiring an operator fetch or a surviving canonical worktree. Add regression tests where the remote branch is pushed after the managed clone's last fetch, exact SHA fetch succeeds, remote tip differs from submitted head, commit is unavailable, repeated recovery is idempotent, and no CI-fix label is added for fetch infrastructure failures. Acceptance criteria: the OOMPAH-704 reproduction gates 5640fc49e without manual fetch; OOMPAH-700's non-canonical submission promise holds across stale managed clones; focused exact-head/standalone submission tests, terminal mutation scan, and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 21:51
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-08-02 21:51
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 21:52
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/opus]
- Turns: 1, Tool calls: 0
- Tokens: 6 in / 664 out [670 total]
- Cost: $0.0000
- Exit: normal, Duration: 23s
- Log: OOMPAH-705__20260802T215147Z.jsonl
---
author: oompah
created: 2026-08-02 21:52
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-02 21:52
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-02 21:52
---
Understanding: I will inspect the existing OOMPAH-705 review branch and its failing CI logs, reproduce the actual failure locally, then make the smallest tested correction to exact-head recovery/review gating, push the same branch, verify rerun state, and submit the task.
---
author: oompah
created: 2026-08-02 21:56
---
Discovery: OOMPAH-700 lets BranchQualityGate archive an exact object from the managed clone, but _review_quality_gate_passes still derives expected_head only from local origin/<branch> or a local branch before any fetch. A clean external submission therefore persists integration.head_sha yet produces Head: unknown in a stale managed clone. The standalone authority already probes the live remote and fences advancement, so the correction must use the persisted integration head, materialize/verify its remote-tracking ref with authenticated bounded Git, and retain stale-head/infrastructure fail-closed routing.
---
author: oompah
created: 2026-08-02 22:01
---
Implementation: Standalone delivery now compares the live remote branch tip with the accepted integration.head_sha before review lookup, so a newer tip cannot replace submitted evidence. Review gating resolves the persisted submission head, uses the project-scoped credential path for a 30-second exact branch-ref fetch into the stale managed clone, verifies the fetched tip equals the accepted SHA, reuses an already materialized exact ref idempotently, and classifies unavailable/fetch failures as infrastructure_error without CI-fix mutation. Added stale-clone, newer-tip, unavailable-head, idempotence, and standalone admission regressions.
---
author: oompah
created: 2026-08-02 22:14
---
Verification: PASS — 96/96 quality-gate + standalone delivery tests; 13/13 submit-focused worker/CLI tests; terminal mutation scan 6/6 allowlisted. Full isolated xdist run: 15,013 passed, 7 skipped, 1 expected xfail, with one unrelated parallel-only failure in test_pr_merged_stages_task_merged; that test passes alone and the complete tests/test_server_webhooks.py file passes 130/130. The make targets themselves could not bootstrap because the host Snap uv wrapper fails in DBus before setup, so the same Makefile runner and scanner were executed directly with the provisioned interpreter.
---
author: oompah
created: 2026-08-02 22:15
---
Completion: Delivered commit 73e20b64c on pushed branch OOMPAH-705. Accepted standalone submission heads are now remote-verified, credential-fetched into stale managed clones, exact-tip checked before CI, and protected from newer-head substitution; infrastructure fetch failures do not create CI-fix state. Regression coverage includes stale-clone recovery, repeated idempotence, advanced remote tips, unavailable commits, and standalone pre-gate fencing.
---
author: oompah
created: 2026-08-02 22:15
---
Fetched and fenced accepted standalone submission heads before review quality gating, with stale-clone and infrastructure regression coverage.
---
author: oompah
created: 2026-08-02 22:15
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 77
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 23m 18s
- Log: OOMPAH-705__20260802T215243Z.jsonl
---
author: oompah
created: 2026-08-02 22:31
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-705`
Target: `main`
Head: `73e20b64c99a542bbbab3c84237af916193b1a7c`
Command: `make test`
Result: `infrastructure_error`

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Trusted quality-gate runtime corruption detected; candidate CI was not run: trusted editable source mapping is inconsistent: expected one of ['/home/shedwards/src/oompah'] or immutable candidate /home/shedwards/.oompah/tmp/oompah-quality-gate-gd2niz_9/workspace; actual /home/shedwards/.oompah/worktrees/oompah/OOMPAH-701. Repair or replace the service test runtime before rerunning the branch gate.
```
---
author: oompah
created: 2026-08-02 23:46
---
Branch quality gate passed for `73e20b64c99a542bbbab3c84237af916193b1a7c` using `make test` in 423.0s. Review creation may proceed.
---
author: oompah
created: 2026-08-02 23:55
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-02 23:55
---
YOLO: merged PR #666.
---
author: oompah
created: 2026-08-02 23:57
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-02 23:57
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 23:57
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 0, Tool calls: 8
- Tokens: 17 in / 217 out [234 total]
- Cost: $0.0000
- Exit: terminated, Duration: 48s
- Log: OOMPAH-705__20260802T235710Z.jsonl
---
author: oompah
created: 2026-08-02 23:58
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
<!-- COMMENTS:END -->
