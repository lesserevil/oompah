---
id: OOMPAH-504
type: feature
status: In Validation
priority: 1
title: Compact agent prompt history around actionable handoffs
parent: OOMPAH-502
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T15:06:00.486812Z'
updated_at: '2026-08-04T21:48:52.330978Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 17064e28-3674-428b-9136-b50d49aa289f
oompah.work_branch: epic-OOMPAH-502
oompah.task_costs:
  total_input_tokens: 1542042
  total_output_tokens: 12401
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1187311
      output_tokens: 5652
      cost_usd: 0.0
    sonnet:
      input_tokens: 354731
      output_tokens: 6749
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1187311
    output_tokens: 5652
    cost_usd: 0.0
    recorded_at: '2026-07-28T17:46:50.679958+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 354698
    output_tokens: 5950
    cost_usd: 0.0
    recorded_at: '2026-07-28T17:49:24.424039+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 33
    output_tokens: 799
    cost_usd: 0.0
    recorded_at: '2026-07-28T17:52:33.885793+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a4497cc05587
    project_id: proj-14849f1b
    task_id: OOMPAH-504
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9cdac45e193220a608ea9c2cb7c7de0c9366e23d9601e844d60283aaf8e2215d
    attempts:
    - version: 1
      attempt_id: attempt-afa9bc724024
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9cdac45e193220a608ea9c2cb7c7de0c9366e23d9601e844d60283aaf8e2215d
      created_at: '2026-08-04T21:41:22.223915+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:41:22.223915+00:00'
      branch_key: epic-OOMPAH-502
      ended_at: '2026-08-04T21:48:51.031305+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T18:28:07.309771+00:00'
    updated_at: '2026-08-04T21:41:22.223915+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-afa9bc724024
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9cdac45e193220a608ea9c2cb7c7de0c9366e23d9601e844d60283aaf8e2215d
    created_at: '2026-08-04T21:41:22.223915+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:41:22.223915+00:00'
    branch_key: epic-OOMPAH-502
    ended_at: '2026-08-04T21:48:51.031305+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
---
## Summary

Problem: every dispatch injects every prior task comment into WORKFLOW.md. Multi-focus tasks accumulate long progress, test, and completion comments, forcing each fresh agent to replay stale context and increasing provider latency/tokens.

Implementation: add a deterministic prompt-comment compactor before render_prompt. Always retain the newest human-authored instruction/question, the latest Focus handoff comment, Needs Human instructions when present, and the most recent comments within configurable count and byte budgets. Insert a trusted omission notice with omitted count and tell the agent to use oompah task view for full history. Preserve chronological order, author/timestamp metadata, untrusted-content provenance wrapping, mid-run comment delivery, and the full canonical tracker history. Add OOMPAH_PROMPT_MAX_COMMENTS and OOMPAH_PROMPT_MAX_COMMENT_BYTES to .env.example with conservative defaults; do not put tunables in WORKFLOW.md.

Tests: add unit tests for retention priority, ordering, deduplication, byte/count limits, enormous single comments, all-human histories, latest handoff outside the recent window, Needs Human final questions, and prompt-injection delimiters. Add orchestrator integration tests proving only compacted comments reach render_prompt while tracker storage is untouched.

Acceptance criteria: prompt size is bounded; no latest actionable human request or focus handoff is lost; full history remains retrievable; provenance/security tests and focused tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:06
---
Claimed for manual implementation by the current Codex session. Held in Backlog while the shared epic branch is built so Oompah does not dispatch another agent; status will move to In Progress and Done as this session completes the slice.
---
author: oompah
created: 2026-07-28 15:12
---
Implementing a pure, non-mutating comment compactor at the three initial-prompt paths. It will retain latest human context, latest Focus handoff, the final Needs Human instruction, and recent comments within count/byte caps; a renderer-only trusted omission notice will point agents to the full task history.
---
author: oompah
created: 2026-07-28 15:16
---
Implemented and pushed in commit 85be456eb. Fresh agent prompts now compact comment history without mutating tracker storage, retain prioritized human/handoff/Needs Human context plus recent comments, include a trusted full-history notice, preserve untrusted provenance, and support environment-only count/byte caps. Focused prompt/config/provenance suite: 439 passed.
---
author: oompah
created: 2026-07-28 15:16
---
Startup task history is bounded and actionable context is retained; canonical tracker history and provenance remain intact.
---
author: oompah
created: 2026-07-28 17:44
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 17:44
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 17:46
---
Agent completed successfully in 147s (1192963 tokens)
---
author: oompah
created: 2026-07-28 17:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 17
- Tokens: 1.2M in / 5.7K out [1.2M total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 27s
- Log: OOMPAH-504__20260728T174426Z.jsonl
---
author: oompah
created: 2026-07-28 17:46
---
Agent completed without closing this issue (147s (1192963 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-28 17:47
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 17:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 17:49
---
Focus handoff: duplicate_detector

Outcome: no separate duplicate was found. The exact OOMPAH-504 implementation is already present in commit c1eb096e2 (feat: compact startup prompt history), which is an ancestor of the current epic-OOMPAH-502 head and explicitly references OOMPAH-504.

Evidence: searched task history, plans/docs, and all git history for prompt/comment compaction; no other task matches the complete scope. The implementation spans oompah/prompt.py, oompah/orchestrator.py, oompah/config.py, .env.example, and focused tests.

Verification: .venv/bin/python -m pytest tests/test_prompt_comment_compaction.py tests/test_config.py tests/test_provenance.py -q => 411 passed.

Remaining work/risk: feature/finalization focus should assess the already-landed implementation against acceptance criteria and close OOMPAH-504 if satisfied. Recommended next focus: feature.
---
author: oompah
created: 2026-07-28 17:49
---
Agent completed successfully in 132s (360648 tokens)
---
author: oompah
created: 2026-07-28 17:49
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 17
- Tokens: 354.7K in / 6.0K out [360.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 12s
- Log: OOMPAH-504__20260728T174714Z.jsonl
---
author: oompah
created: 2026-07-28 17:49
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 17:49
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 17:49
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-28 17:49
---
Security Auditor understanding: Reviewing the comment compactor implementation (landed in commit c1eb096e2) for OOMPAH-504. Primary security concerns: (1) prompt injection — untrusted comment content must remain wrapped in provenance delimiters through the compaction pipeline; (2) trusted-notice spoofing — an attacker could craft a comment mimicking the trusted omission notice to manipulate agent behavior; (3) prioritization bypass — malicious content in a comment that looks like a Focus handoff or Needs Human message might escape the untrusted tier; (4) resource exhaustion — pathological byte/count configurations or enormous single comments. Will audit oompah/prompt.py, oompah/orchestrator.py, oompah/config.py, .env.example, and the test suite.
---
author: oompah
created: 2026-07-28 17:52
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 18
- Tokens: 33 in / 799 out [832 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 58s
- Log: OOMPAH-504__20260728T174938Z.jsonl
---
author: oompah
created: 2026-07-28 17:54
---
Restored after patch-equivalent commit 85be456eb was verified on the rebased epic branch; prompt compaction remains fully implemented and tested.
---
author: oompah
created: 2026-08-04 18:28
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
