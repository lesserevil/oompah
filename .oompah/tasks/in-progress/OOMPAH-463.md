---
id: OOMPAH-463
type: feature
status: In Progress
priority: 1
title: Persist terminal-audit state through the tracker metadata contract
parent: OOMPAH-457
children: []
blocked_by:
- OOMPAH-462
- OOMPAH-452
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:05:05.235115Z'
updated_at: '2026-07-28T18:50:34.548554Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 6b481f50-63b9-4f13-b105-3bb0e917194f
oompah.work_branch: epic-OOMPAH-457
oompah.task_costs:
  total_input_tokens: 884025
  total_output_tokens: 5192
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 884025
      output_tokens: 5192
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 884025
    output_tokens: 5192
    cost_usd: 0.0
    recorded_at: '2026-07-28T18:41:59.044747+00:00'
---
## Summary

Implementation scope

Add tracker-neutral helpers that read and write a single namespaced oompah.terminal_audit metadata document containing the pending chain and bounded audit-attempt history. Use TrackerProtocol.get_metadata/set_metadata_field and the per-project write lock; do not parse human comments as authority. Implement no-op detection so polling does not create metadata-only commits when the document is unchanged. Cover native Markdown, GitHub body metadata, and GitLab metadata once the GitLab adapter is available. Preserve unknown future fields during updates.

Tests

Add contract tests for empty metadata, round trips, append/update, no-op writes, unknown-field preservation, concurrent serialized updates, malformed-document quarantine, and secret redaction for each tracker adapter. Run focused tests and make test.

Acceptance criteria

Audit state survives process restart and tracker rereads, concurrent writers cannot silently drop attempts, unchanged writes are true no-ops, and no secret or full model response reaches tracker metadata.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:39
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:39
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 18:40
---
Understanding: I will screen existing oompah tasks and project documentation for terminal-audit/tracker-metadata work, then read each plausible candidate's full description and comments. If no duplicate is confirmed, I will record the closest reviewed tasks and evidence, add the duplicate-detector completion label, and hand off for implementation without changing code.
---
author: oompah
created: 2026-07-28 18:41
---
Discovery: Duplicate screening found no confirmed duplicate. Exact searches across .oompah/tasks, docs, plans, README.md, and WORKFLOW.md found no prior terminal_audit, pending-chain, audit-attempt, or metadata-contract task. Full task views reviewed: OOMPAH-462 (Done) defines tracker-neutral audit records/fingerprints only; OOMPAH-452 (Merged) restores GitLab adapter metadata support only; OOMPAH-464 covers service_state.json grandfather baselines/recovery; OOMPAH-465 covers transition staging/chains. These are dependencies/consumers with distinct acceptance criteria, not duplicates. Existing source primitives are TrackerProtocol.get_metadata/set_metadata_field in oompah/tracker.py, the per-project lock in oompah/projects.py, and the completed terminal_audit domain in oompah/terminal_audit.py; no terminal-audit persistence helper exists.
---
author: oompah
created: 2026-07-28 18:41
---
Focus handoff: duplicate_detector\n\nOutcome: No duplicate confirmed; OOMPAH-463 remains a distinct implementation task.\n\nEvidence and decisions: Searched with rg for terminal-audit, terminal_audit, audit-attempt, pending chain, tracker metadata, metadata contract, malformed-document, secret redaction, terminal, and audit across .oompah/tasks, docs, plans, README.md, and WORKFLOW.md. Read full task descriptions/comments for OOMPAH-462, OOMPAH-452, OOMPAH-464, OOMPAH-465, plus closest historical candidates OOMPAH-28, OOMPAH-29, OOMPAH-173, OOMPAH-194, OOMPAH-219, OOMPAH-253, and OOMPAH-257. OOMPAH-462 supplies domain types; OOMPAH-452 supplies the GitLab adapter; OOMPAH-464 owns service-state upgrade/recovery; OOMPAH-465 owns transition orchestration. None covers the requested tracker-neutral oompah.terminal_audit document, unknown-field-preserving updates, no-op detection, per-project lock serialization, malformed quarantine, or adapter contract/redaction tests. Relevant current primitives/files: oompah/terminal_audit.py, oompah/tracker.py (TrackerProtocol metadata methods), oompah/projects.py (project_write_lock), and existing adapter tests.\n\nRemaining work/risks: implement and test the metadata helper across native Markdown, GitHub body metadata, and the now-available GitLab adapter; ensure concurrent read-modify-write operations cannot lose attempts, unchanged writes make no tracker mutation, malformed metadata is quarantined safely, and secrets/model prose never enter tracker metadata.\n\nRecommended next focus: feature (backend implementation), with OOMPAH-452 and OOMPAH-462 treated as completed prerequisites.
---
author: oompah
created: 2026-07-28 18:41
---
Agent completed successfully in 124s (889217 tokens)
---
author: oompah
created: 2026-07-28 18:42
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 30
- Tokens: 884.0K in / 5.2K out [889.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 4s
- Log: OOMPAH-463__20260728T184000Z.jsonl
---
author: oompah
created: 2026-07-28 18:42
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 18:42
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 18:42
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 18:42
---
Understanding: I will add a tracker-neutral terminal-audit metadata helper backed by oompah.terminal_audit, use the project write lock for serialized read-modify-write operations, preserve unknown fields, quarantine malformed data, redact persisted values, and cover native/GitHub/GitLab behavior with focused tests before committing and closing the task.
---
author: oompah
created: 2026-07-28 18:50
---
Implementation: Added oompah/terminal_audit_metadata.py. TerminalAuditMetadataStore persists one versioned oompah.terminal_audit envelope with pending_chain and bounded attempt_history, updates it under ProjectStore.project_write_lock, skips unchanged writes, preserves forward-compatible fields (including nested record fields), and quarantines malformed payloads using only a SHA-256 marker. It never reads comments and redacts credentials/model-response-like data before persistence. Added adapter contract tests for native Markdown, GitHub body, and GitLab metadata.
---
<!-- COMMENTS:END -->
