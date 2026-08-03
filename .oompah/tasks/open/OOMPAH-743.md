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
updated_at: '2026-08-03T23:01:13.803547Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0ae3cd2b870ee78371f5e7a470f3aee5387883b8a71b045614a482e967161c2b
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 63f887cc-ed35-4fc2-8df1-1eb44a49ffce
  claim_owner: a032ecbf-d61c-48ca-9cba-cbf452c15431
  claimed_at: '2026-08-03T23:01:04.556759+00:00'
  claim_expires_at: '2026-08-03T23:31:04.556759+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3d19e877-4539-4f82-b20a-1134b903984a
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

