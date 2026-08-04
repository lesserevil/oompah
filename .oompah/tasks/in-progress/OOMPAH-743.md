---
id: OOMPAH-743
type: bug
status: In Progress
priority: 1
title: Keep raw failure transcripts out of dashboard alert summaries
parent: OOMPAH-740
children: []
blocked_by:
- OOMPAH-741
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T22:56:22.560635Z'
updated_at: '2026-08-04T14:08:09.216422Z'
work_branch: epic-OOMPAH-740--task-OOMPAH-743
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0ae3cd2b870ee78371f5e7a470f3aee5387883b8a71b045614a482e967161c2b
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T23:04:28.651892+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Closest active tasks are OOMPAH-741 (actionability classification),\
    \ OOMPAH-742 (compact alert-center layout), OOMPAH-744 (stale UI reconciliation),\
    \ and OOMPAH-745 (browser regression coverage). They are related but do not duplicate\
    \ the specific producer/renderer transcript sanitization and bounded-summary problem\
    \ in OOMPAH-743.\nFocus handoff: duplicate_detector  \nDuplicate preflight verdict:\
    \ no_duplicate  \nMatches: none  \n\nEvidence: Closest active tasks are OOMPAH-741\
    \ (actionability classification), OOMPAH-742 (compact alert-center layout), OOMPAH-744\
    \ (stale UI reconciliation), and OOMPAH-745 (browser regression coverage). They\
    \ are related but do not duplicate the specific producer/renderer transcript sanitization\
    \ and bounded-summary problem in OOMPAH-743."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d0b56b50-a47c-4c03-967a-05ec328dbfda
oompah.work_branch: epic-OOMPAH-740--task-OOMPAH-743
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-740--task-OOMPAH-743
  base_branch: epic-OOMPAH-740
  base_sha: d3cc87e7f273decdf492d48dfaba027cc815ef5a
  updated_at: '2026-08-04T13:53:11.992054+00:00'
oompah.task_costs:
  total_input_tokens: 46297
  total_output_tokens: 288
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46297
      output_tokens: 288
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46297
    output_tokens: 288
    cost_usd: 0.0
    recorded_at: '2026-08-03T23:04:28.637889+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-743__20260803T230232Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-740--task-OOMPAH-743
    source_sha: 583fb236963493a820f36eabdd29789fa5497e6b
    completed_at: '2026-08-03T23:04:28.666659+00:00'
---
## Summary

Prevent multiline subprocess, git, provider, and exception transcripts from expanding the dashboard header or always-visible alert summary while keeping useful diagnostics available on demand.

Scope:
- Produce concise structured titles and summaries for integration, audit, gate, and transport failures.
- Store or reference sanitized detailed output separately from the compact presentation fields.
- Normalize whitespace and line breaks, enforce explicit length limits at both producer and renderer boundaries, and use deterministic truncation with an accessible indication that more detail exists.
- Never expose secrets, authorization headers, token material, unredacted provider output, or unsafe HTML.
- In expanded alert details, show a concise explanation and remediation first; make the bounded diagnostic transcript secondary.
- Reproduce the EXOCOMP-147 rebase-conflict case from the production screenshot as a regression fixture.

Relevant files: integration and health alert producers in oompah/, oompah/templates/dashboard.html, redaction helpers, and focused alert rendering tests.

Required tests:
- Long multiline git rebase output becomes a one-line bounded summary.
- Sanitized detail remains available through the explicit details view.
- Newlines, control characters, HTML, and credential-like values cannot break layout or bypass escaping and redaction.
- Very long Unicode input truncates predictably.
- Existing concise alerts remain readable.

Acceptance criteria:
- No raw transcript can wrap across the agent bar or compact alert-center summary.
- Full useful context remains available without logs being the only diagnostic source.
- Presentation limits and redaction are enforced defensively on both sides of the API boundary.
- Focused security and dashboard tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 23:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 23:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 23:04
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.3K in / 288 out [46.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 48s
- Log: OOMPAH-743__20260803T230232Z.jsonl
---
author: oompah
created: 2026-08-03 23:12
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 23:12
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-03 23:13
---
Understanding: keep multiline failure transcripts out of compact dashboard alerts by producing bounded normalized/redacted summaries, retaining sanitized diagnostics for explicit details, and enforcing safe limits at producer and renderer boundaries. I will trace producers/templates, add regression/security tests including the EXOCOMP-147 rebase case, run focused checks, then commit, push, and submit.
---
author: oompah
created: 2026-08-03 23:17
---
Discovery: Orchestrator.get_snapshot() currently publishes _alerts verbatim; integration_retry alerts concatenate IntegrationExecutionResult.message, which can contain multiline rebase/gate transcripts. Server cached/IPC snapshots can bypass that producer. I will enforce a shared redacted/normalized/bounded alert projection at both boundaries, add a structured integration failure alert, and render diagnostics only inside an accessible collapsed details control.
---
author: oompah
created: 2026-08-03 23:26
---
Verification: focused alert/dashboard/integration coverage passes (91 tests, then 40 alert/dashboard tests after final renderer hardening); snapshot/WS/API responsiveness suites pass (59 tests); integration executor and parallel-child integration suites pass (48 tests); auth/audit/credential suites pass (110 tests); automatic-rebase/quality-gate checks pass (6 tests). The initial Unicode fixture assertion was corrected to exceed the diagnostic bound.
---
author: oompah
created: 2026-08-03 23:34
---
Implementation: added shared alert_safety projections that redact credentials, normalize control characters and whitespace, bound compact fields and diagnostics, and preserve structured failure metadata. Integration failures now publish concise title/summary/detail/action fields with bounded diagnostics. Snapshot enrichment re-sanitizes cached/IPC alerts, and the dashboard uses bounded escaped text with accessible collapsed diagnostic details and no-wrap compact styling. Added EXOCOMP-147 rebase, Unicode, redaction, API-boundary, and renderer regression coverage.
---
author: oompah
created: 2026-08-03 23:36
---
Completion: delivered bounded, redacted alert projections across integration producers, snapshot/API enrichment, and dashboard rendering. Compact alerts are normalized one-line fields with explicit limits; sanitized diagnostics are available in escaped collapsed details with explanation/action first. Added EXOCOMP-147, Unicode, credential/control/HTML, API-boundary, and renderer regression tests. Full gate: 15,224 passed, 7 skipped, 1 xfailed; check-secrets and diff checks passed. Commit d5e1c80ab pushed.
---
author: oompah
created: 2026-08-03 23:36
---
Bound dashboard alert summaries and preserved sanitized diagnostics
---
author: oompah
created: 2026-08-03 23:37
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 101
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 25m 7s
- Log: OOMPAH-743__20260803T231234Z.jsonl
---
author: oompah
created: 2026-08-04 13:52
---
Integration found a rebase conflict on `epic-OOMPAH-740--task-OOMPAH-743`. Resolve it against `epic-OOMPAH-740`, run the required tests, push the same private branch, and `oompah task submit` it again.
---
author: oompah
created: 2026-08-04 13:53
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-04 13:53
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-04 13:53
---
Understanding: I will trace integration/health failure data from producers through the dashboard contract and renderer, reconcile OOMPAH-741 first, then enforce redacted one-line bounded compact fields plus separately bounded expandable diagnostics. I will add regression/security tests for EXOCOMP-147-style rebase output, escaping/control characters/credential redaction, Unicode truncation, and existing concise alerts, while avoiding overlapping orchestrator paths unless necessary.
---
author: oompah
created: 2026-08-04 14:00
---
Discovery: The rebase conflict came from OOMPAH-741 introducing dashboard_alerts.normalize_alerts as the canonical actionability/deduplication contract while the prior OOMPAH-743 commit added a parallel alert sanitizer. I reconciled the interfaces by retaining OOMPAH-741's canonical contract and layering transcript-aware redaction/bounds beneath it. Integration retry production, snapshot normalization, and REST/WebSocket enrichment now share that path; the renderer remains a separate defensive boundary.
---
author: oompah
created: 2026-08-04 14:03
---
Implementation: Reconciled the alert sanitizer with OOMPAH-741's dashboard fact contract instead of replacing its actionability fields. Added bounded/redacted payload projection, one-line compact aliases, separately bounded diagnostics, structured integration failure fields, producer/snapshot/API defense in depth, renderer-side Unicode/control normalization and limits, no-wrap agent-bar styling, escaped native details rendering with explanation/remediation first, and a reusable EXOCOMP-147 rebase transcript fixture.
---
author: oompah
created: 2026-08-04 14:07
---
Verification: Post-rebase focused suites pass: 432 alert-contract, transcript security/redaction, health, integration retry/executor, webhook, and dashboard tests; 149 state snapshot, IPC, WebSocket, and API responsiveness tests; make check-secrets passes. make test-setup itself is unavailable in this managed worker because the configured Snap uv launcher fails to create a transient DBus scope, so the configured orchestrator full branch gate will run on the exact submitted head.
---
author: oompah
created: 2026-08-04 14:08
---
Completion: Rebased and reconciled OOMPAH-743 onto OOMPAH-741 at exact pushed head f745082a0. Delivered canonical bounded/redacted alert facts without losing actionability, structured integration failures, sanitized expandable diagnostics, defensive renderer limits/escaping/no-wrap presentation, and the EXOCOMP-147 fixture. Post-rebase evidence: 432 focused alert/security/health/integration tests and 149 snapshot/WebSocket/API tests pass; check-secrets and diff checks pass.
---
<!-- COMMENTS:END -->
