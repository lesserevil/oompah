---
id: OOMPAH-743
type: bug
status: Open
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
updated_at: '2026-08-03T23:04:35.859645Z'
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
oompah.agent_run_id: 3d19e877-4539-4f82-b20a-1134b903984a
oompah.work_branch: epic-OOMPAH-740--task-OOMPAH-743
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-740--task-OOMPAH-743
  base_branch: epic-OOMPAH-740
  base_sha: 583fb236963493a820f36eabdd29789fa5497e6b
  updated_at: '2026-08-03T23:02:02.231402+00:00'
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
<!-- COMMENTS:END -->
