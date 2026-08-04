---
id: OOMPAH-747
type: bug
status: Ready to Integrate
priority: 1
title: Reuse trusted patch-equivalence evidence during epic auto-close
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T00:40:39.779884Z'
updated_at: '2026-08-04T00:57:35.446784Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
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
  total_input_tokens: 46741
  total_output_tokens: 179
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46741
      output_tokens: 179
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46741
    output_tokens: 179
    cost_usd: 0.0
    recorded_at: '2026-08-04T00:42:11.694581+00:00'
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
<!-- COMMENTS:END -->
