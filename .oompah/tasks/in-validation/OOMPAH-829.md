---
id: OOMPAH-829
type: bug
status: In Validation
priority: 1
title: Migrate legacy equivalent Done-override fingerprints for structural maintenance
  tasks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T13:24:24.014858Z'
updated_at: '2026-08-05T19:51:17.785878Z'
work_branch: OOMPAH-829
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/723
review_number: '723'
review_head: 8c262588c86e873665bc92fe0b885f6d734412bf
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1551768186f6e7b315b12d3550594c1936f9f224777cfb8422e99a4316fd63d5
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T18:25:26.053098+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active peer task in the authoritative corpus describes\
    \ this migration. Closest tasks OOMPAH-156, OOMPAH-162, and OOMPAH-165 are terminal\
    \ and address different fingerprint-deduplication or epic-merge behaviors.\nFocus\
    \ handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate  \n\
    Matches: none\n\nEvidence: No active peer task in the authoritative corpus describes\
    \ this migration. Closest tasks OOMPAH-156, OOMPAH-162, and OOMPAH-165 are terminal\
    \ and address different fingerprint-deduplication or epic-merge behaviors."
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
  total_input_tokens: 48365
  total_output_tokens: 8864
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 48324
      output_tokens: 274
      cost_usd: 0.0
    unknown:
      input_tokens: 41
      output_tokens: 8590
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 48324
    output_tokens: 274
    cost_usd: 0.0
    recorded_at: '2026-08-05T18:25:26.042207+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 41
    output_tokens: 8590
    cost_usd: 0.0
    recorded_at: '2026-08-05T19:50:34.286479+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-829__20260805T181841Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: duplicate_detector
    source_branch: OOMPAH-829
    source_sha: b53bdbc77c7a50d332a97096ebc85d7923280854
    completed_at: '2026-08-05T18:25:26.100920+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-829
  head_sha: 8c262588c86e873665bc92fe0b885f6d734412bf
  submitted_at: '2026-08-05T19:08:30.124055+00:00'
  updated_at: '2026-08-05T19:08:30.124055+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/723
oompah.review_number: '723'
oompah.work_branch: OOMPAH-829
oompah.target_branch: main
oompah.review_head: 8c262588c86e873665bc92fe0b885f6d734412bf
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-d4736e35fc68: '2026-08-05T19:50:00.559090+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-829
    target_state: Done
    evidence_fingerprint: 6d4ce17424480a510530e13b63a9b8d6b439bbec3840a24140bbf26a277c620e
    audit_ids:
    - audit-d628e5e4235c
    kind: result
    applied: true
    retired_at: '2026-08-05T19:50:00.559098+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-829
    audit_id: audit-d628e5e4235c
    attempt_id: attempt-d4736e35fc68
    target_state: Done
    evidence_fingerprint: 6d4ce17424480a510530e13b63a9b8d6b439bbec3840a24140bbf26a277c620e
    status: In Validation
    audit_ids:
    - audit-d628e5e4235c
    applied: true
    created_at: '2026-08-05T19:50:00.559108+00:00'
    applied_at: '2026-08-05T19:50:08.281427+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-d628e5e4235c
    project_id: proj-14849f1b
    task_id: OOMPAH-829
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6d4ce17424480a510530e13b63a9b8d6b439bbec3840a24140bbf26a277c620e
    attempts:
    - version: 1
      attempt_id: attempt-d4736e35fc68
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 6d4ce17424480a510530e13b63a9b8d6b439bbec3840a24140bbf26a277c620e
      created_at: '2026-08-05T19:34:46.396368+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T19:34:46.396368+00:00'
      branch_key: OOMPAH-829
      verdict: pass
      completed_at: '2026-08-05T19:50:00.558985+00:00'
      ended_at: '2026-08-05T19:50:00.558985+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-05T19:32:10.611419+00:00'
    updated_at: '2026-08-05T19:50:00.558985+00:00'
  - version: 1
    audit_id: audit-fbd06944968b
    project_id: proj-14849f1b
    task_id: OOMPAH-829
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6d4ce17424480a510530e13b63a9b8d6b439bbec3840a24140bbf26a277c620e
    attempts:
    - version: 1
      attempt_id: attempt-ff5b6f66f9b8
      target_state: Merged
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 6d4ce17424480a510530e13b63a9b8d6b439bbec3840a24140bbf26a277c620e
      created_at: '2026-08-05T19:51:16.243903+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T19:51:16.243903+00:00'
      branch_key: OOMPAH-829
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-05T19:32:10.611419+00:00'
    updated_at: '2026-08-05T19:51:16.243903+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-d4736e35fc68
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6d4ce17424480a510530e13b63a9b8d6b439bbec3840a24140bbf26a277c620e
    created_at: '2026-08-05T19:34:46.396368+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T19:34:46.396368+00:00'
    branch_key: OOMPAH-829
  - version: 1
    attempt_id: attempt-ff5b6f66f9b8
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6d4ce17424480a510530e13b63a9b8d6b439bbec3840a24140bbf26a277c620e
    created_at: '2026-08-05T19:51:16.243903+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T19:51:16.243903+00:00'
    branch_key: OOMPAH-829
---
## Summary

Triggered by: OOMPAH-825

Live acceptance failure after deploying OOMPAH-825 on exact main 7978ec91b5532784c5dd6f18bc028954fd3696a9: OOMPAH-662 repaired from Merged to Done, but OOMPAH-660 remains Merged with lifecycle_repair_not_applied. OOMPAH-660 is the original OOMPAH-663 fingerprint-canonicalization reproduction. Its current integrated issue fingerprint and original integration-staged Done audit are ab40139d2035 at exact integrated SHA 793bcc7969d39634dab560ed0a10b9dcad7a9716, while its applied authorized Done override and duplicate no-auditor request carry legacy normalized/API fingerprint 62954f9b5fdc. OOMPAH-825's live-shaped test incorrectly modeled the override as already equal to the current fingerprint, so the promised 660 repair cannot occur. Implementation scope: add a bounded, explicit legacy-equivalence migration for structurally Done-only direct epic maintenance rows. Reconstruct both known canonical snapshot shapes from durable integration metadata (integration-staged integrated base/head/contributor shape and legacy normalized API/work-branch shape); accept an applied Done override only when its digest equals one reconstructed shape, the current digest equals the other, exact project/task/target/authorized/applied fields match, immutable integrated SHA/branch evidence is unchanged, current state is Merged, and the Merged validator still rejects it as Done-only under the project lock. Persist the equivalence/migration version before the one Done write, then retire only the exact child's incompatible Merged metadata. Never accept arbitrary fingerprint drift, comment/reason text, missing integration evidence, CI-fix/merge-conflict tasks, retired/superseded overrides, or SCM outage. Relevant code: terminal_audit.py canonical fingerprint variants/history from OOMPAH-663; terminal_audit_enforcement.py lifecycle authority and locked repair; live OOMPAH-660 metadata. Required tests: exact production-shaped OOMPAH-660 ab401↔62954 pair repairs once; OOMPAH-662 current-match control; one-field changes to integrated SHA, base branch, task identity, target, override authority/application, or structural classification fail closed; restart/crash intent recovery and cross-project isolation. Acceptance: OOMPAH-660 alone moves Merged to Done exactly once without manual task/ledger edits, row completes/reconciled and stays idempotent, unrelated historical overrides remain rejected, lifecycle warning converges clear, focused fingerprint/enforcement/coordinator tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 18:18
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-08-05 18:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 18:25
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 48.3K in / 274 out [48.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 7m 2s
- Log: OOMPAH-829__20260805T181841Z.jsonl
---
author: oompah
created: 2026-08-05 18:29
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-05 18:29
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-05 18:30
---
Understanding: Treating this as a CI repair on the existing OOMPAH-829 branch. I will inspect the current review head and actual failing job logs, reproduce the failure, apply the smallest covered fix, run focused project checks, then push and verify the rerun before submission.
---
author: oompah
created: 2026-08-05 18:36
---
Discovery: No PR or Actions run exists for OOMPAH-829; the branch is a clean origin/main head, so the reported live acceptance case is the concrete failure. In terminal_audit_enforcement.py, _lifecycle_terminal_authorities requires an applied override to equal compute_issue_evidence_fingerprint(), which rejects OOMPAH-660's durable legacy digest. I inspected the read-only native task metadata and reproduced the exact pair from the same issue/integration record: canonical integrated ab40139d20357c96... versus legacy work-branch 62954f9b5fdcde92.... The two shapes differ only by the OOMPAH-729 integrated canonicalization (base/integrated SHA plus task-branch contributor versus work-branch/head SHA).
---
author: oompah
created: 2026-08-05 18:43
---
Implementation: Added an explicit integrated-evidence fingerprint-variant reconstruction in terminal_audit.py and a v1 legacy Done-override equivalence fence in terminal_audit_enforcement.py. Only one active/applied, schema-valid Done override with exact project/task/target/authorized fields and the reconstructed legacy digest can qualify; current evidence must equal the reconstructed integrated digest and the task must remain a non-CI/non-conflict direct epic rebase helper. Under the project lock, the Merged conflict is revalidated, the complete equivalence/integration intent is durably checkpointed before the Done write, and restart recovery re-derives the marker before finalizing only the exact child's incompatible Merged metadata.
---
author: oompah
created: 2026-08-05 19:07
---
Verification: focused fingerprint/enforcement/coordinator suites passed (240 passed). The correctly provisioned full branch gate passed via make test: 15,682 passed, 7 skipped, 1 xfailed, 44 warnings in 650.32s; terminal mutation scan also passed. The initial Snap/DBus uv bootstrap issue was bypassed with the existing project venv, and the prior environment-only subprocess checks independently passed (35 passed, 5 skipped).
---
author: oompah
created: 2026-08-05 19:08
---
Completion: delivered and pushed commit 8c262588c86e873665bc92fe0b885f6d734412bf on OOMPAH-829. The migration reconstructs only the durable integrated/work-branch fingerprint pair, checkpoints versioned equivalence before the one Done mutation, revalidates authority during locked execution and crash recovery, and retires only exact task-scoped incompatible Merged metadata. Production-shaped OOMPAH-660, OOMPAH-662 control, fail-closed drift/outage/classification, restart recovery, idempotence, and cross-project isolation are covered. Branch is clean and matches origin; GitHub has no pre-existing PR or Actions run for this branch.
---
author: oompah
created: 2026-08-05 19:08
---
Migrated bounded legacy-equivalent Done override fingerprints for structural maintenance tasks with durable intent/recovery, exact metadata retirement, and production-shaped fail-closed coverage. Focused and full Makefile gates pass; pushed 8c262588c86e873665bc92fe0b885f6d734412bf.
---
author: oompah
created: 2026-08-05 19:08
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 108
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 38m 59s
- Log: OOMPAH-829__20260805T183002Z.jsonl
---
author: oompah
created: 2026-08-05 19:20
---
Branch quality gate passed for `8c262588c86e873665bc92fe0b885f6d734412bf` using `make test` in 634.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-05 19:32
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-05 19:32
---
YOLO: merged PR #723.
---
author: oompah
created: 2026-08-05 19:35
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 19:35
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 19:50
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_sha: 8c262588c86e873665bc92fe0b885f6d734412bf
- target_branch_head: da53569a9
- pr_merged: true
- focused_tests: fingerprint=10 enforcement=95 coordinator=135 audit=38 override=28 lifecycle=52 queue=27 executor=16 all_pass
- commit_scope: oompah/terminal_audit.py, oompah/terminal_audit_enforcement.py, tests/test_terminal_audit_enforcement.py, tests/test_terminal_fingerprint_canonicalization.py
- migration_version: LEGACY_DONE_OVERRIDE_EQUIVALENCE_VERSION=1
- acceptance_scenarios: OOMPAH-660 repairs once and is idempotent; OOMPAH-662 control needs no marker; 12 fail-closed drift cases; SCM outage fails closed; post-write recovery; cross-project isolation
---
author: oompah
created: 2026-08-05 19:50
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 46, Tool calls: 35
- Tokens: 41 in / 8.6K out [8.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 15m 32s
- Log: OOMPAH-829__20260805T193509Z.jsonl
---
<!-- COMMENTS:END -->
