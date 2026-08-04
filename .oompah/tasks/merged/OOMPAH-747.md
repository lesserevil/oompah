---
id: OOMPAH-747
type: bug
status: Merged
priority: 1
title: Reuse trusted patch-equivalence evidence during epic auto-close
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T00:40:39.779884Z'
updated_at: '2026-08-04T02:01:56.668909Z'
work_branch: OOMPAH-747
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/697
review_number: '697'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1f9c08d70a8de1c46153484200e417859077a231cd898475c6e870568917d478
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T00:42:11.699007+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active non-terminal task matches this issue. The closest\
    \ reviewed tasks\u2014OOMPAH-162, OOMPAH-165, and OOMPAH-168\u2014are terminal\
    \ Archived items and address related but distinct epic-landing behavior.\nFocus\
    \ handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate  \n\
    Matches: none  \n\nEvidence: No active non-terminal task matches this issue. The\
    \ closest reviewed tasks\u2014OOMPAH-162, OOMPAH-165, and OOMPAH-168\u2014are\
    \ terminal Archived items and address related but distinct epic-landing behavior."
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
  total_input_tokens: 46829
  total_output_tokens: 2736
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46741
      output_tokens: 179
      cost_usd: 0.0
    unknown:
      input_tokens: 88
      output_tokens: 2557
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46741
    output_tokens: 179
    cost_usd: 0.0
    recorded_at: '2026-08-04T00:42:11.694581+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 286
    cost_usd: 0.0
    recorded_at: '2026-08-04T01:36:39.237092+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 36
    output_tokens: 1141
    cost_usd: 0.0
    recorded_at: '2026-08-04T01:40:04.978723+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 36
    output_tokens: 910
    cost_usd: 0.0
    recorded_at: '2026-08-04T01:44:30.434915+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 10
    output_tokens: 220
    cost_usd: 0.0
    recorded_at: '2026-08-04T02:01:54.272683+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-747__20260804T004147Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-747
    source_sha: 4ea94b151a09758c57a93c8710c05f28a49bcc2a
    completed_at: '2026-08-04T00:42:11.720378+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-747
  head_sha: a8a9e2b2f51a581f9066736a9408f21adacffed5
  submitted_at: '2026-08-04T00:57:27.794052+00:00'
  updated_at: '2026-08-04T00:57:27.794052+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/697
oompah.review_number: '697'
oompah.work_branch: OOMPAH-747
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-83223ba19bd7: '2026-08-04T01:36:09.804907+00:00'
    attempt-e4a37a126bae: '2026-08-04T02:00:38.982684+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-747
    target_state: Done
    evidence_fingerprint: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
    audit_ids:
    - audit-862f2d92c639
    kind: result
    applied: true
    retired_at: '2026-08-04T01:36:09.804917+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-747
    target_state: Merged
    evidence_fingerprint: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
    audit_ids:
    - audit-d960e1cbd976
    kind: result
    applied: true
    retired_at: '2026-08-04T02:00:38.982702+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-747
    audit_id: audit-862f2d92c639
    attempt_id: attempt-83223ba19bd7
    target_state: Done
    evidence_fingerprint: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
    status: In Validation
    audit_ids:
    - audit-862f2d92c639
    applied: true
    created_at: '2026-08-04T01:36:09.804928+00:00'
    applied_at: '2026-08-04T01:36:14.879740+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-747
    audit_id: audit-d960e1cbd976
    attempt_id: attempt-e4a37a126bae
    target_state: Merged
    evidence_fingerprint: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
    status: Merged
    audit_ids:
    - audit-d960e1cbd976
    applied: true
    created_at: '2026-08-04T02:00:38.982721+00:00'
    applied_at: '2026-08-04T02:00:47.583594+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-862f2d92c639
    project_id: proj-14849f1b
    task_id: OOMPAH-747
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
    attempts:
    - version: 1
      attempt_id: attempt-83223ba19bd7
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
      created_at: '2026-08-04T01:27:11.035096+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T01:27:11.035096+00:00'
      branch_key: OOMPAH-747
      verdict: pass
      completed_at: '2026-08-04T01:36:09.804792+00:00'
      ended_at: '2026-08-04T01:36:09.804792+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-04T01:25:39.651146+00:00'
    updated_at: '2026-08-04T01:36:09.804792+00:00'
  - version: 1
    audit_id: audit-d960e1cbd976
    project_id: proj-14849f1b
    task_id: OOMPAH-747
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
    attempts:
    - version: 1
      attempt_id: attempt-6a3fccee8ff6
      target_state: Merged
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
      created_at: '2026-08-04T01:36:57.795384+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T01:36:57.795384+00:00'
      branch_key: OOMPAH-747
      failure_classification: policy_incompatibility
      ended_at: '2026-08-04T01:40:10.470846+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy permits only read-only repository inspection and
        configured test commands; command denied'
      next_retry_at: '2026-08-04T01:40:20.470817+00:00'
    - version: 1
      attempt_id: attempt-bc243a0566c1
      target_state: Merged
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
      created_at: '2026-08-04T01:41:41.800357+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T01:41:41.800357+00:00'
      branch_key: OOMPAH-747
      candidate_rotation_count: 1
      failure_classification: policy_incompatibility
      ended_at: '2026-08-04T01:44:32.262739+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy permits only read-only repository inspection and
        configured test commands; command denied'
      next_retry_at: '2026-08-04T01:44:52.262712+00:00'
    - version: 1
      attempt_id: attempt-e4a37a126bae
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
      created_at: '2026-08-04T01:44:55.190871+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-04T01:44:55.190871+00:00'
      branch_key: OOMPAH-747
      candidate_rotation_count: 2
      verdict: pass
      completed_at: '2026-08-04T02:00:38.982510+00:00'
      ended_at: '2026-08-04T02:00:38.982510+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-04T01:25:39.651146+00:00'
    updated_at: '2026-08-04T02:00:38.982510+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-83223ba19bd7
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
    created_at: '2026-08-04T01:27:11.035096+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T01:27:11.035096+00:00'
    branch_key: OOMPAH-747
  - version: 1
    attempt_id: attempt-6a3fccee8ff6
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
    created_at: '2026-08-04T01:36:57.795384+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T01:36:57.795384+00:00'
    branch_key: OOMPAH-747
    failure_classification: policy_incompatibility
    ended_at: '2026-08-04T01:40:10.470846+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy permits only read-only repository inspection and configured
      test commands; command denied'
    next_retry_at: '2026-08-04T01:40:20.470817+00:00'
  - version: 1
    attempt_id: attempt-bc243a0566c1
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
    created_at: '2026-08-04T01:41:41.800357+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T01:41:41.800357+00:00'
    branch_key: OOMPAH-747
    candidate_rotation_count: 1
    failure_classification: policy_incompatibility
    ended_at: '2026-08-04T01:44:32.262739+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy permits only read-only repository inspection and configured
      test commands; command denied'
    next_retry_at: '2026-08-04T01:44:52.262712+00:00'
  - version: 1
    attempt_id: attempt-e4a37a126bae
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6a3ce33c5f518abe994746e794f18baa65c9fdea45bfd1d9547187421ba5181b
    created_at: '2026-08-04T01:44:55.190871+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-04T01:44:55.190871+00:00'
    branch_key: OOMPAH-747
    candidate_rotation_count: 2
---
## Summary

Triggered by: EXOCOMP-130

Live reproduction: EXOCOMP-130 cannot auto-close because child EXOCOMP-148 records integrated SHA 8400a54a, while the current epic branch contains operator-verified rebased equivalents 61141cb8 and 9663f4b2. Epic review coverage recognizes this class through OOMPAH-519, but the earlier child-landing auto-close check still requires exact ancestry and reports two unlanded commits. Implementation scope: reuse the trusted patch-equivalence proof path for child landing and epic auto-close instead of maintaining a stricter duplicate resolver; when equivalence is proven, persist or consume canonical rebased integration evidence without weakening fail-closed behavior. Relevant code includes epic auto-close, _child_landing_evidence_block_reason, shared-epic review coverage, integration metadata reconciliation, and branch evidence helpers in oompah/orchestrator.py and project storage. Required tests: reproduce EXOCOMP-148 with changed commit SHAs after a direct epic rebase; cover multi-commit docs plus implementation patches, trusted and untrusted evidence, truly missing patches, deleted private refs, restart idempotence, and no regression to OOMPAH-519. Acceptance criteria: trusted patch-equivalent completed children unblock epic auto-close; unproven or ambiguous content remains blocked with precise evidence; one canonical proof implementation serves review coverage and auto-close.

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
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.7K in / 179 out [46.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 40s
- Log: OOMPAH-747__20260804T004147Z.jsonl
---
author: oompah
created: 2026-08-04 00:44
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 00:44
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-04 00:44
---
Understanding: reuse the existing trusted patch-equivalence proof for child landing and epic auto-close, preserve fail-closed behavior for untrusted/ambiguous/missing evidence, add regression coverage for rebases and restart/idempotence, then verify and submit.
---
author: oompah
created: 2026-08-04 00:56
---
Implementation: consolidated ancestry/patch-equivalence proof in _reported_commit_landed_on_refs with full base_sha..head ranges; reused it for durable integration/queue evidence and Oompah-authored completion evidence; wired _child_landing_evidence_block_reason into shared rollup and epic auto-close; added precise stuck-epic evidence details and regressions for deleted refs, two rebased docs/implementation patches, and missing patches.
---
author: oompah
created: 2026-08-04 00:56
---
Verification: 27 epic auto-close tests passed; 233 epic-strategy tests passed; merged/reconciliation/terminal-contract group passed 202 with 1 expected xfail; integration/parallel/landing group passed 57. Direct pytest needed --import-mode=importlib because the ambient environment points tests.conftest at another checkout; compileall and diff checks are clean.
---
author: oompah
created: 2026-08-04 00:57
---
Completion: shipped commit a8a9e2b2f and pushed branch OOMPAH-747. Epic auto-close and shared rollup landing now reuse trusted, range-complete patch-equivalence evidence; rebased multi-commit work unblocks only when all patches are proven, while missing/untrusted evidence remains blocked with precise diagnostics. Focused verification is green.
---
author: oompah
created: 2026-08-04 00:57
---
Reuse canonical trusted range-aware patch-equivalence evidence for shared epic landing and epic auto-close; add rebased multi-commit and missing-patch regressions.
---
author: oompah
created: 2026-08-04 00:57
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 91
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 13m 35s
- Log: OOMPAH-747__20260804T004436Z.jsonl
---
author: oompah
created: 2026-08-04 01:16
---
Branch quality gate passed for `a8a9e2b2f51a581f9066736a9408f21adacffed5` using `make test` in 411.9s. Review creation may proceed.
---
author: oompah
created: 2026-08-04 01:25
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-04 01:25
---
YOLO: merged PR #697.
---
author: oompah
created: 2026-08-04 01:27
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 01:27
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 01:36
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- merge_commit: c54a60a63a1742fa0dfa4ad2a68f46cc61d87fdf
- implementation_commit: a8a9e2b2f51a581f9066736a9408f21adacffed5
- pr: #697
- changed_files: oompah/orchestrator.py (+255/-80), tests/test_epic_auto_close.py (+172)
- focused_tests: test_epic_auto_close.py=27 pass; test_epic_strategy.py=233 pass; combined epic+terminal+duplicate=335 pass
- branch_gate: make test 411.9s green (per prior gate comment)
- acceptance_criteria: canonical proof reused (auto-close + rollup + durable); range-complete equivalence prevents tip-only false positives; stuck-epic alert now includes precise child evidence reason
---
author: oompah
created: 2026-08-04 01:36
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 36, Tool calls: 26
- Tokens: 6 in / 286 out [292 total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 26s
- Log: OOMPAH-747__20260804T012722Z.jsonl
---
author: oompah
created: 2026-08-04 01:37
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 01:37
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 01:40
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 21
- Tokens: 36 in / 1.1K out [1.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 59s
- Log: OOMPAH-747__20260804T013712Z.jsonl
---
author: oompah
created: 2026-08-04 01:40
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
author: oompah
created: 2026-08-04 01:41
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 01:41
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 01:44
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 0, Tool calls: 19
- Tokens: 36 in / 910 out [946 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 46s
- Log: OOMPAH-747__20260804T014150Z.jsonl
---
author: oompah
created: 2026-08-04 01:44
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
author: oompah
created: 2026-08-04 01:45
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-04 01:45
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 02:00
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- merge_commit: c54a60a63a1742fa0dfa4ad2a68f46cc61d87fdf
- implementation_commit: a8a9e2b2f51a581f9066736a9408f21adacffed5
- pr: #697
- changed_files: oompah/orchestrator.py (+255/-80), tests/test_epic_auto_close.py (+172)
- focused_tests: test_epic_auto_close.py=27 pass; test_epic_strategy.py=233 pass
- branch_gate: make test 411.9s green (per prior gate comment)
- regression_tests: test_rebased_multi_commit_integration_evidence_unblocks_auto_close PASS; test_rebased_multi_commit_missing_patch_blocks_auto_close PASS
- acceptance_criteria: canonical proof reused (auto-close + rollup + durable); range-complete equivalence prevents tip-only false positives; stuck-epic alert now includes precise child evidence reason
---
author: oompah
created: 2026-08-04 02:01
---
Run #3 [attempt=3, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 42
- Tokens: 10 in / 220 out [230 total]
- Cost: $0.0000
- Exit: terminated, Duration: 16m 56s
- Log: OOMPAH-747__20260804T014506Z.jsonl
---
<!-- COMMENTS:END -->
