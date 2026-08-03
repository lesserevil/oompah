---
id: OOMPAH-736
type: bug
status: Open
priority: 1
title: Align auditor command policy with project-required Makefile validation targets
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T19:26:22.477120Z'
updated_at: '2026-08-03T19:27:41.637758Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a9ad7e8cca59e0c39ddf67181fa80efd012d0a7ebcde6adf3c86742955b010cb
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T19:27:32.123320+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed the supplied peer corpus; no active task addresses\
    \ auditor command-policy validation or provider-rotation classification. Closest\
    \ topics, OOMPAH-174 and OOMPAH-175, are archived release-branch tasks and unrelated.\n\
    Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none\n\nEvidence: Reviewed the supplied peer corpus; no active task\
    \ addresses auditor command-policy validation or provider-rotation classification.\
    \ Closest topics, OOMPAH-174 and OOMPAH-175, are archived release-branch tasks\
    \ and unrelated."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 1fb75a12-8871-435f-81b9-a2b0f12cda68
oompah.task_costs:
  total_input_tokens: 50398
  total_output_tokens: 297
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 50398
      output_tokens: 297
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 50398
    output_tokens: 297
    cost_usd: 0.0
    recorded_at: '2026-08-03T19:27:31.988008+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-736__20260803T192705Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-736
    source_sha: fae232ee614a74a9565f4fc6bfbbcf86333f0255
    completed_at: '2026-08-03T19:27:32.147847+00:00'
---
## Summary

Triggered by: EXOCOMP-159

Production regression observed on EXOCOMP-159. The task requires make test, make fmt-check, and make lint. Its first independent auditor successfully ran the configured make test gate, but the read-only auditor command policy denied which mix, a focused mix test, and make fmt-check. The second independent auditor was likewise denied make help and a focused mix test. Two denials terminate an attempt, so both eligible candidates were exhausted and the integrated task moved to Needs Human despite healthy providers and valid repository access.

Root cause context:
- Auditor capability policy permits exact configured test commands plus a narrow inspection catalog.
- Managed-project task requirements and Makefiles can define additional non-mutating validation targets that are not represented in the single configured test command.
- The auditor prompt encourages focused verification and reading available Make targets, but those commands are rejected and counted as policy incompatibilities.
- Candidate rotation cannot recover because every candidate receives the same incompatible local policy.

Implementation scope:
- Define a structured project validation-command contract that includes the configured full gate and explicitly approved non-mutating Makefile targets such as help, fmt-check, lint, and focused test entry points.
- Generate the auditor tool catalog and prompt from the same contract so suggested commands are executable.
- Keep fail-closed parsing: reject shell composition, redirection, command substitution, arbitrary executables, mutating Make targets, and targets not declared safe.
- Do not infer safety from target names alone; require project configuration or validated Makefile metadata under an explicit server policy.
- Distinguish a genuinely forbidden mutation attempt from a policy-contract mismatch in health, attempt rotation, and retry classification.
- A policy-contract mismatch must not consume every independent candidate and strand an otherwise auditable task without a supported automatic recovery path.
- Preserve exact-head detached workspaces, independent-candidate rules, output capture, timeouts, and terminal authority.

Required tests:
- EXOCOMP-159 regression with required make test, make fmt-check, and make lint: every approved target executes and the audit can complete.
- make help or an equivalent approved discovery operation works when declared by the validation contract.
- Focused project tests execute only through an explicitly approved template or Make target.
- Unapproved direct mix, pytest, shell pipelines, redirects, command substitutions, and mutating Make targets remain denied.
- Repeated contract mismatches do not rotate through and exhaust all providers as though they were provider failures.
- Health reports policy-contract incompatibility with task, command class, and remediation while transport health remains separate.
- Restart and configuration reload update the prompt and enforcement catalog atomically.
- Run focused auditor command validation, terminal audit lifecycle, provider rotation, health, and managed-project configuration tests, followed by make test.

Acceptance criteria:
- An auditor can execute every project-required non-mutating validation command advertised in its task and prompt.
- Prompt guidance and enforcement cannot disagree for approved commands.
- EXOCOMP-159-style policy exhaustion no longer sends a healthy integrated task to Needs Human.
- Arbitrary shell and repository mutation remain fail-closed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 19:26
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 19:27
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 19:27
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.4K in / 297 out [50.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 36s
- Log: OOMPAH-736__20260803T192705Z.jsonl
---
<!-- COMMENTS:END -->
