---
id: OOMPAH-706
type: bug
status: In Validation
priority: 1
title: Make duplicate-preflight verdict delivery truncation-proof
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-02T21:55:47.761417Z'
updated_at: '2026-08-03T00:21:36.499399Z'
work_branch: OOMPAH-706
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/667
review_number: '667'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 82145263e666d6ef638c055ad7010f38bff980cdc24ed61b65e79d6555a76293
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-02T23:19:59.002797+00:00'
  matched_identifiers: []
  evidence: 'Project-owner review: OOMPAH-706 is the production regression follow-up
    for OOMPAH-701. The exact provider log proves a complete no-duplicate result was
    lost only by ACP text truncation, and no active task implements this provider-boundary
    envelope repair.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-02T23:19:59.002797+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: 'Project-owner review: OOMPAH-706 is the production regression
    follow-up for OOMPAH-701. The exact provider log proves a complete no-duplicate
    result was lost only by ACP text truncation, and no active task implements this
    provider-boundary envelope repair.'
oompah.agent_run_id: null
oompah.task_costs:
  total_input_tokens: 110782
  total_output_tokens: 5543
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 110758
      output_tokens: 4964
      cost_usd: 0.0
    unknown:
      input_tokens: 24
      output_tokens: 579
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1372
    cost_usd: 0.0
    recorded_at: '2026-08-02T22:07:19.608253+00:00'
  - profile: default
    model: haiku
    input_tokens: 110738
    output_tokens: 2012
    cost_usd: 0.0
    recorded_at: '2026-08-02T22:09:19.796427+00:00'
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1580
    cost_usd: 0.0
    recorded_at: '2026-08-02T22:12:07.079611+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 24
    output_tokens: 579
    cost_usd: 0.0
    recorded_at: '2026-08-03T00:21:31.611607+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-706__20260802T220658Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-706
    source_sha: 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd
    completed_at: '2026-08-02T22:07:19.647136+00:00'
  - run_id: OOMPAH-706__20260802T220834Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-706
    source_sha: 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd
    completed_at: '2026-08-02T22:09:19.824930+00:00'
  - run_id: OOMPAH-706__20260802T221139Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-706
    source_sha: 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd
    completed_at: '2026-08-02T22:12:07.094150+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-706
  head_sha: 0b78028a691b4c21935d9c9dc3b69d59f8448643
  submitted_at: '2026-08-02T23:20:28.116349+00:00'
  updated_at: '2026-08-02T23:20:28.116349+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/667
oompah.review_number: '667'
oompah.work_branch: OOMPAH-706
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f47f6e36b436
    project_id: proj-14849f1b
    task_id: OOMPAH-706
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9eede4aa7940adec0d9d9f608bda4ef4d973f041682049f15fba4b92a7a36e8a
    attempts:
    - version: 1
      attempt_id: attempt-3e5def973c87
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9eede4aa7940adec0d9d9f608bda4ef4d973f041682049f15fba4b92a7a36e8a
      created_at: '2026-08-03T00:20:28.057767+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T00:20:28.057767+00:00'
      branch_key: OOMPAH-706
      failure_classification: infrastructure_error
      ended_at: '2026-08-03T00:21:31.609969+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy denied a mutating or compound shell command; auditors
        cannot edit, commit, push, merge, or change state'
      next_retry_at: '2026-08-03T00:21:41.609938+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T00:19:10.103753+00:00'
    updated_at: '2026-08-03T00:21:31.609969+00:00'
  - version: 1
    audit_id: audit-53320474246e
    project_id: proj-14849f1b
    task_id: OOMPAH-706
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9eede4aa7940adec0d9d9f608bda4ef4d973f041682049f15fba4b92a7a36e8a
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T00:19:10.103753+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-3e5def973c87
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9eede4aa7940adec0d9d9f608bda4ef4d973f041682049f15fba4b92a7a36e8a
    created_at: '2026-08-03T00:20:28.057767+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T00:20:28.057767+00:00'
    branch_key: OOMPAH-706
    failure_classification: infrastructure_error
    ended_at: '2026-08-03T00:21:31.609969+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy denied a mutating or compound shell command; auditors
      cannot edit, commit, push, merge, or change state'
    next_retry_at: '2026-08-03T00:21:41.609938+00:00'
---
## Summary

Triggered by: OOMPAH-701

Production regression observed while dispatching OOMPAH-701 on 2026-08-02 after OOMPAH-682 was merged. Two independent Duplicate Investigator runs both concluded no_duplicate in prose, but each placed the machine-readable verdict after a long narrative and exhausted its response before completing a parseable verdict block. Oompah classified both normal successful exits as inconclusive and scheduled retry delays (60s, then 120s), leaving an otherwise actionable task Open.

Implementation scope:
- Make the duplicate-investigator prompt and transport reserve a small leading structured result envelope before any optional reasoning, and validate that the selected provider/model can comply within its output budget.
- Prefer a typed/tool result or constrained machine-readable channel that cannot be displaced by narrative. If text remains supported, parse a complete leading verdict before optional trailing prose and bound the narrative budget.
- Detect normal provider completion containing an unambiguous no_duplicate conclusion but a missing/truncated contract as a contract/output failure with actionable observability, not an opaque retry.
- Preserve fail-closed behavior against task-comment injection, stale claims, ambiguous prose, and forged verdicts.
- Prevent repeated identical malformed completions from silently consuming the full retry budget; vary/fallback the provider or surface the contract failure explicitly.

Relevant code: oompah/duplicate_screening.py; duplicate-preflight prompt/rendering and finish paths in oompah/orchestrator.py and oompah/focus.py; ACP provider output limits/structured result handling; duplicate-screening metrics and comments.

Required tests:
- A provider that attempts long narrative cannot displace the leading structured no_duplicate verdict.
- A response truncated after a complete leading verdict is accepted, while narrative-only or partial verdict content remains inconclusive.
- Two identical contract failures do not produce an unbounded same-provider retry loop.
- Late/stale output and user-authored comments cannot satisfy the verdict.
- The exact OOMPAH-701 response shape reaches implementation dispatch without owner intervention.

Acceptance criteria:
- Duplicate screening reaches a conclusive result within one normal successful agent completion when the investigator determines no duplicate.
- Output truncation cannot remove the authoritative verdict.
- Contract failures are visible and bounded, with deterministic focused tests and make test/check-secrets passing.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 22:06
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 22:06
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 22:07
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 4, Tool calls: 0
- Tokens: 10 in / 1.4K out [1.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 28s
- Log: OOMPAH-706__20260802T220658Z.jsonl
---
author: oompah
created: 2026-08-02 22:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 22:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 22:09
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 3
- Tokens: 110.7K in / 2.0K out [112.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 49s
- Log: OOMPAH-706__20260802T220834Z.jsonl
---
author: oompah
created: 2026-08-02 22:11
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 22:11
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 22:12
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 32s
- Log: OOMPAH-706__20260802T221139Z.jsonl
---
author: oompah
created: 2026-08-02 22:12
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-706/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-02 22:19
---
Owner-resolved the failed duplicate screening as no_duplicate after reviewing active tasks. Claimed for direct implementation immediately after OOMPAH-701; human-only fences further duplicate-preflight retries. OOMPAH-707 tracks the watchdog defect that currently prevents direct owner work from remaining visibly In Progress without a scheduler RunningEntry.
---
author: oompah
created: 2026-08-02 23:07
---
Direct implementation complete at pushed head 0b78028a691b4c21935d9c9dc3b69d59f8448643. ACP backends now extract a bounded validated duplicate-screening envelope from the full provider response before the 2,000-character display/log cap; the orchestrator consumes that envelope through the existing current-run-only parser, while comments remain excluded. Regression coverage reproduces OOMPAH-701 long analysis followed by a valid verdict and covers Claude, Codex, OpenCode, conflicts, and end-to-end implementation eligibility. Verification: focused 188 passed; full make test 15,017 passed, 7 skipped, 1 xfailed; terminal mutation scan and check-secrets passed. Awaiting deployment of merged OOMPAH-708 solely to execute the authoritative owner-resolution transition out of Needs Human before submit.
---
author: oompah
created: 2026-08-02 23:20
---
Preserved duplicate-screening verdicts before ACP display truncation with bounded provider envelopes across Claude, Codex, and OpenCode. Full make test: 15,017 passed; focused suite, terminal mutation scan, and secret scan passed.
---
author: oompah
created: 2026-08-03 00:10
---
Branch quality gate passed for `0b78028a691b4c21935d9c9dc3b69d59f8448643` using `make test` in 394.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-03 00:19
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-03 00:19
---
YOLO: merged PR #667.
---
author: oompah
created: 2026-08-03 00:20
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 00:20
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-03 00:21
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 11
- Tokens: 24 in / 579 out [603 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 2s
- Log: OOMPAH-706__20260803T002035Z.jsonl
---
author: oompah
created: 2026-08-03 00:21
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
<!-- COMMENTS:END -->
