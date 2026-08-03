---
id: OOMPAH-728
type: bug
status: In Validation
priority: 1
title: Keep structurally relevant peers in duplicate-screening corpus
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T16:19:05.113116Z'
updated_at: '2026-08-03T17:34:20.013947Z'
work_branch: OOMPAH-728
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/684
review_number: '684'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: aea388b18a2c0faefa7f6c16fe1e122e4f6edc0ef800d6cd8f961e34bff6159e
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T16:21:03.011564+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: This is a new, project-specific regression about the\
    \ Duplicate Investigator's corpus construction and evidence retention. No existing\
    \ task in the current project corpus addresses corpus builder relevance selection,\
    \ structurally significant peer retention, or the EXOCOMP-216/EXOCOMP-221 regression.\
    \ Related archived tasks (OOMPAH-10 through OOMPAH-175) focus on webhooks, dashboard,\
    \ intake validation, and epic workflows\u2014entirely different subsystems. OOMPAH-728\
    \ requires focused implementation work on a previously untracked issue.\nI need\
    \ to investigate whether OOMPAH-728 is a duplicate of an existing task in the\
    \ project. Let me analyze this carefully.\n\n## Understanding OOMPAH-728\n\nThis\
    \ issue describes a production regression in the Duplicate Investigator's corpus\
    \ construction:\n- Agents screening EXOCOMP-216 and EXOCOMP-221 returned inconclusive\
    \ results\n- The corpus omitted active sibling tasks needed for comparison\n-\
    \ Agents exhausted retry budget and tasks were moved to Needs Human\n- The fix\
    \ requires: retaining structurally relevant peers, preventing unreachable loopback\
    \ calls, providing actionable diagnostics\n\nThis is specifically about the **duplicate-screening\
    \ corpus builder** - how it selects and prioritizes which tasks to include when\
    \ investigating whether a task is a duplicate.\n\n## Reviewing the Project Task\
    \ Corpus\n\nI've reviewed the provided authoritative task corpus containing all\
    \ project tasks. The corpus includes:\n\n**Active/Open tasks:**\n- OOMPAH-728\
    \ (current task - Open)\n\n**Archived/Completed tasks:**\n- OOMPAH-10 through\
    \ OOMPAH-175: Various infrastructure, dashboard, intake, and epic workflow fixes\n\
    - None of these address corpus construction for duplicate screening\n- None reference\
    \ the Duplicate Investigator's evidence gathering\n- None address the regression\
    \ with EXOCOMP-216/EXOCOMP-221\n\n**Key searches:**\n- \"corpus\" - appears only\
    \ in OOMPAH-728\n- \"duplicate.*screen\" or \"screening\" - appears only in OOMPAH-728\n\
    - \"EXOCOMP-216\" or \"EXOCOMP-221\" - appears only in OOMPAH-728\n- \"structurally\
    \ relevant peers\" - appears only in OOMPAH-728\n\nThe closest related task is\
    \ OOMPAH-682 (referenced in the acceptance criteria about investigators receiving\
    \ enough evidence), but it doesn't appear in the corpus and likely addresses a\
    \ different acceptance criterion.\n\n## Conclusion\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: This\
    \ is a new, project-specific regression about the Duplicate Investigator's corpus\
    \ construction and evidence retenti"
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
  total_input_tokens: 54
  total_output_tokens: 10306
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1698
      cost_usd: 0.0
    unknown:
      input_tokens: 44
      output_tokens: 8608
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1698
    cost_usd: 0.0
    recorded_at: '2026-08-03T16:21:03.010806+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 44
    output_tokens: 8608
    cost_usd: 0.0
    recorded_at: '2026-08-03T17:34:17.864260+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-728__20260803T162028Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-728
    source_sha: d510748342777dd4748070d83391ffb0eae40091
    completed_at: '2026-08-03T16:21:03.049403+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-728
  head_sha: 2d682cacc8e9f18a6fc12de674b7ac91f37532e1
  submitted_at: '2026-08-03T16:53:21.950339+00:00'
  updated_at: '2026-08-03T16:53:21.950339+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/684
oompah.review_number: '684'
oompah.work_branch: OOMPAH-728
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-260b0c89c00a: '2026-08-03T17:33:46.602018+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-728
    target_state: Done
    evidence_fingerprint: cbf62bc583bb9518cc3fcb30f87c4c893b12b8d1074cc02d49da7e934e4d08fa
    audit_ids:
    - audit-3dc00ff3f23c
    kind: result
    applied: true
    retired_at: '2026-08-03T17:33:46.602032+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-728
    audit_id: audit-3dc00ff3f23c
    attempt_id: attempt-260b0c89c00a
    target_state: Done
    evidence_fingerprint: cbf62bc583bb9518cc3fcb30f87c4c893b12b8d1074cc02d49da7e934e4d08fa
    status: In Validation
    audit_ids:
    - audit-3dc00ff3f23c
    applied: true
    created_at: '2026-08-03T17:33:46.602052+00:00'
    applied_at: '2026-08-03T17:33:53.951343+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-3dc00ff3f23c
    project_id: proj-14849f1b
    task_id: OOMPAH-728
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cbf62bc583bb9518cc3fcb30f87c4c893b12b8d1074cc02d49da7e934e4d08fa
    attempts:
    - version: 1
      attempt_id: attempt-260b0c89c00a
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: cbf62bc583bb9518cc3fcb30f87c4c893b12b8d1074cc02d49da7e934e4d08fa
      created_at: '2026-08-03T17:20:06.888630+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T17:20:06.888630+00:00'
      branch_key: OOMPAH-728
      verdict: pass
      completed_at: '2026-08-03T17:33:46.601790+00:00'
      ended_at: '2026-08-03T17:33:46.601790+00:00'
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-03T17:19:05.983776+00:00'
    updated_at: '2026-08-03T17:33:46.601790+00:00'
  - version: 1
    audit_id: audit-1543f6417c72
    project_id: proj-14849f1b
    task_id: OOMPAH-728
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cbf62bc583bb9518cc3fcb30f87c4c893b12b8d1074cc02d49da7e934e4d08fa
    attempts: []
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-03T17:19:05.983776+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-260b0c89c00a
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cbf62bc583bb9518cc3fcb30f87c4c893b12b8d1074cc02d49da7e934e4d08fa
    created_at: '2026-08-03T17:20:06.888630+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T17:20:06.888630+00:00'
    branch_key: OOMPAH-728
---
## Summary

Triggered by: EXOCOMP-216

Production regression observed on 2026-08-03 while screening EXOCOMP-216 and EXOCOMP-221. Three independent Duplicate Investigator runs for each task returned inconclusive because the injected tracker-backed corpus omitted the active sibling tasks needed for comparison. The agents explicitly named the missing peers (EXOCOMP-209 and EXOCOMP-213 through EXOCOMP-218 for EXOCOMP-216; EXOCOMP-219 through EXOCOMP-224 for EXOCOMP-221). One run then tried the scoped task CLI at http://localhost:8090 even though its sandbox had no reachable server. Both valid tasks exhausted the bounded retry budget and were moved to Needs Human. This violates OOMPAH-682's acceptance criterion that investigators receive enough authoritative active-task evidence to reach a verdict.

Implementation scope:
- Reproduce corpus construction for EXOCOMP-216 and EXOCOMP-221 against a project with more tasks than the corpus budget.
- Make relevance selection retain structurally relevant active peers before generic truncation: parent/children/siblings, declared dependencies and hard-start dependencies, and title/description similarity candidates.
- Include enough task description and relevant comment evidence for a conclusive comparison, while retaining deterministic size bounds and treating all task text as untrusted.
- Do not instruct or rely on a sandboxed investigator to query an unreachable loopback service; either make the injected corpus self-sufficient or provide a supported authenticated read-only transport and advertise only capabilities actually available.
- Expose an actionable diagnostic when required peers cannot fit the corpus instead of consuming three indistinguishable model retries.

Required tests:
- Large-corpus regressions modeled on EXOCOMP-216 and EXOCOMP-221 prove every same-parent sibling and dependency relevant to screening is present.
- Deterministic budget tests prove unrelated tasks are evicted before structurally relevant peers.
- A network-disabled investigator prompt remains self-sufficient and does not require CLI fallback.
- Corpus entries preserve status, description, and bounded relevant comments.
- Existing prompt-injection, revision-fingerprint, late-claim, retry, and owner-resolution tests continue to pass.
- Run focused duplicate-preflight/prompt tests and make test.

Acceptance criteria:
- Each reproduced task reaches a conclusive screening verdict in one normal run using only supplied evidence.
- No valid task reaches Needs Human solely because relevant active peers were dropped by corpus selection.
- Corpus size remains bounded, deterministic, project-scoped, and safe for untrusted task text.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 16:20
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 16:20
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 16:21
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 41s
- Log: OOMPAH-728__20260803T162028Z.jsonl
---
author: oompah
created: 2026-08-03 16:21
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 16:21
---
Focus: Security Auditor
---
author: oompah
created: 2026-08-03 16:22
---
Understanding: I will trace duplicate-preflight corpus construction and investigator prompt generation, reproduce the large-project sibling/dependency omission, then implement deterministic structural relevance and bounded evidence while preserving untrusted-text isolation and network-disabled self-sufficiency. I will add regression tests, run focused checks and the Makefile gate, then commit, push, and submit.
---
author: oompah
created: 2026-08-03 16:25
---
Discovery: _duplicate_preflight_task_corpus currently sorts all scoped tasks by state/identifier, then truncates at 100 tasks and breaks on the first byte overflow. It ignores parent/child/sibling/dependency relationships and description similarity. Issue already carries parent_id, blocked_by, and start_blocked_by, so the fix can rank authoritative tracker records without worker checkout or network fallback.
---
author: oompah
created: 2026-08-03 16:30
---
Implementation: Reworked duplicate corpus selection to retain the current task, parent/children/siblings, direct and reverse normal/hard-start dependencies, then title/description similarity candidates before deterministic generic fallback. Added bounded row compaction, stable project scoping/deduplication, comments/status/description evidence, and an explicit insufficient-budget diagnostic. Duplicate investigators are told the corpus is self-sufficient with no CLI/HTTP/loopback fallback; read-only ACP catalogs expose only workspace file tools.
---
author: oompah
created: 2026-08-03 16:33
---
Verification update: focused duplicate-preflight, focus, and prompt suites pass (226 passed). The corpus output was manually checked at 32,394 bytes with 203 peers and 100 selected rows, below the 96 KiB cap; required peers were all retained and generic/similarity candidates were bounded deterministically. I am proceeding with the complete Makefile gate and final security review.
---
author: oompah
created: 2026-08-03 16:43
---
Verification: focused duplicate-preflight/focus/prompt plus ACP and prompt-injection suites pass (354 passed). Repository fallback full suite passes (15,130 passed, 7 skipped, 1 xfailed, 41 warnings); terminal-mutation scan passes (6/6 allowlisted); make check-secrets passes. Direct make test setup was attempted twice but blocked before pytest by host uv DBus transient-scope failure, and documented gate mode correctly rejected a runtime launcher from another checkout.
---
author: oompah
created: 2026-08-03 16:52
---
Verification: focused duplicate-preflight/prompt, injection, ACP, and retry suites pass (355 tests); the exact final head passed the full repository gate via the pre-provisioned test runner: 15131 passed, 7 skipped, 1 xfailed, 45 warnings. git diff --check is clean. The normal make test wrapper remains blocked by the host uv transient-scope DBus error before pytest; its documented gate mode also rejected the non-candidate runtime, so the repository's isolated test runner was used for complete coverage.
---
author: oompah
created: 2026-08-03 16:53
---
Completion: delivered and pushed commit 2d682cacc. Duplicate screening now prioritizes current-task structure (parent, children, siblings, dependencies/hard-start dependencies) and title/description similarity within deterministic task/byte bounds, preserves bounded descriptions/comments/status, emits actionable insufficiency diagnostics, and keeps the investigator self-sufficient with no CLI/network fallback. Added regression, budget, diagnostics, and prompt capability tests plus screening documentation.
---
author: oompah
created: 2026-08-03 16:53
---
Retain structurally relevant peers in bounded duplicate-screening corpora with actionable insufficiency diagnostics and self-sufficient investigator prompts; tests and documentation added.
---
author: oompah
created: 2026-08-03 16:53
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 117
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 31m 58s
- Log: OOMPAH-728__20260803T162146Z.jsonl
---
author: oompah
created: 2026-08-03 17:09
---
Branch quality gate passed for `2d682cacc8e9f18a6fc12de674b7ac91f37532e1` using `make test` in 430.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-03 17:19
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-03 17:19
---
YOLO: merged PR #684.
---
author: oompah
created: 2026-08-03 17:20
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 17:20
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-03 17:33
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_sha: 2d682cacc8e9f18a6fc12de674b7ac91f37532e1
- merge_commit_on_main: 14df3a875
- changed_files: docs/duplicate-screening.md; oompah/acp_tools.py; oompah/focus.py; oompah/orchestrator.py; tests/test_duplicate_preflight.py; tests/test_focus.py
- diff_stats: 6 files changed, 680 insertions(+), 37 deletions(-)
- focused_tests_passed: test_duplicate_preflight.py=44; test_focus.py=141; test_orchestrator_duplicate_detection.py=25; test_epic_strategy.py[duplicate_preflight]=4; test_prompt_injection_protection.py=29; test_auditor_contract.py[acp_catalogs]=2; test_secrets.py=116
- corpus_bounds: MAX_TASKS=100; MAX_BYTES=96 KiB; MAX_DIAGNOSTIC_IDS=32
- structural_relevance_reasons: parent; child; same_parent_sibling; hard_start_dependency; dependency; hard_start_dependent; dependent
- self_sufficient_prompt: must_do updated to forbid oompah task CLI/curl/HTTP/localhost/loopback fallback; read-only tool catalogs restrict duplicate_detector to read_file/list_files/search_files
- branch_gate_prior_run: make test passed for 2d682cacc in 430.7s (per prior comment 2026-08-03 17:09)
---
author: oompah
created: 2026-08-03 17:34
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 48, Tool calls: 38
- Tokens: 44 in / 8.6K out [8.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 13m 59s
- Log: OOMPAH-728__20260803T172029Z.jsonl
---
<!-- COMMENTS:END -->
