---
id: OOMPAH-729
type: bug
status: In Review
priority: 1
title: Rearm terminal audit after evidence-only remediation on the same head
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T16:23:52.854950Z'
updated_at: '2026-08-03T17:54:45.139416Z'
work_branch: OOMPAH-729
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/686
review_number: '686'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 47992fd656f08c8452820e2fdc13ebbee52ed2bbb24cb99c6969456badd42a6f
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T16:25:05.468060+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Duplicate preflight verdict: no_duplicate\nMatches: none\n\
    Based on my review of the authoritative project task corpus, I will now provide\
    \ my findings:\n\n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight\
    \ verdict: no_duplicate\n\nMatches: none\n\nEvidence:\n\nOOMPAH-729 describes\
    \ a unique production regression: a terminal audit failure on an integrated task\
    \ (EXOCOMP-145) that cannot be recovered when evidence-only remediation is supplied\
    \ (make test/fmt-check/lint outputs added without code changes). The issue is\
    \ characterized by:\n- Unchanged implementation head and canonical code fingerprint\n\
    - \"already completed\" log message preventing fresh audits\n- Integration sweep\
    \ deadlock (task stuck in Ready to Integrate indefinitely)\n- Need for authenticated,\
    \ explicit audit rearmament with fail-closed security\n\nI reviewed all active\
    \ and terminal tasks in the corpus. No existing task\u2014archived or open\u2014\
    addresses this specific problem:\n- OOMPAH-160 covers atomic task writes and corrupt\
    \ file detection, not audit rearmament\n- OOMPAH-156 covers error_watcher deduplication,\
    \ not terminal audit recovery\n- OOMPAH-577/OOMPAH-720 (referenced as related\
    \ context) are not shown in corpus but are prerequisites/context\n- All workflow/audit-adjacent\
    \ tasks (OOMPAH-159, OOMPAH-164, etc.) address different aspects (intake normalization,\
    \ documentation, epic workflow)\n\nThis is a novel production regression requiring\
    \ its own implementation to:\n1. Reproduce evidence-only audit failure scenarios\n\
    2. Add authenticated audit rearmament API\n3. Integrate recovery with integration\
    \ completion sweep\n4. Preserve security and ownership boundaries\n\nOOMPAH-729\
    \ is an original issue requiring implementation work, not a duplicate."
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
  total_input_tokens: 10
  total_output_tokens: 1942
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1942
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1942
    cost_usd: 0.0
    recorded_at: '2026-08-03T16:25:05.466875+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-729__20260803T162427Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-729
    source_sha: d510748342777dd4748070d83391ffb0eae40091
    completed_at: '2026-08-03T16:25:05.503912+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-729
  head_sha: e4b2865eaff689389c35305372785511457b9cd9
  submitted_at: '2026-08-03T17:17:25.200083+00:00'
  updated_at: '2026-08-03T17:17:25.200083+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/686
oompah.review_number: '686'
oompah.work_branch: OOMPAH-729
oompah.target_branch: main
---
## Summary

Triggered by: EXOCOMP-145

Production regression observed on EXOCOMP-145. The task was integrated successfully at b0d047ea97d00deb5c9b83054ddfb6de1491f0a9, but its last independent Done audit failed only because the required pinned Makefile gate output was missing. The operator subsequently ran make test, make fmt-check, and make lint successfully on that exact pushed head and recorded the raw tails. No code change was needed. Every integration completion sweep now logs 'Integrated task EXOCOMP-145 could not enter terminal audit: already completed' and leaves the task Ready to Integrate forever. OOMPAH-577 permits a fresh audit only when the evidence fingerprint changes; OOMPAH-720 intentionally excludes comments and audit bookkeeping from that fingerprint. The result is no automatic or ordinary audited recovery path for valid evidence-only remediation.

Implementation scope:
- Reproduce a failed terminal audit whose implementation head and canonical code fingerprint remain unchanged while required operator/quality-gate evidence is subsequently supplied.
- Add an authenticated, explicit, race-safe way to supersede the failed record and enqueue one fresh audit for the same target/fingerprint when remediation is evidence-only.
- Integrate that recovery with the integration completion sweep so an integrated task cannot log 'already completed' indefinitely without an actionable state, alert, or supported rearm operation.
- Preserve fail-closed behavior for unchanged incomplete work: arbitrary comments and non-owner actors must not rearm audits, and a successful completed audit must remain idempotently final.
- Preserve audit history, actor/reason attribution, independent-candidate requirements, ownership fencing, and exact task/integrated SHA evidence.
- Consider extending the existing owner --audit-retry path beyond infrastructure-only exhaustion with an explicit evidence-addendum contract rather than inventing a parallel terminal mutation.

Required tests:
- EXOCOMP-145 regression: failed missing-evidence audit, same integrated SHA, authenticated evidence remediation, fresh Pending/In Validation audit, then PASS to Done.
- Non-owner and arbitrary-comment attempts cannot rearm.
- Repeated identical owner rearm requests coalesce and cannot create duplicate auditors.
- Genuine code/evidence fingerprint changes continue through OOMPAH-577 behavior.
- Previously successful same-fingerprint audits remain non-rearmable.
- Sweep/restart races converge without repeated warning spam or a Ready-to-Integrate deadlock.
- Run focused terminal coordinator/API/integration tests and make test.

Acceptance criteria:
- An integrated same-head task can recover from an evidence-only audit failure through one documented authenticated action and return to independent audit.
- The integration sweep never leaves such a task indefinitely Ready with only an 'already completed' log line.
- No implementation or terminal authority boundary is weakened.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 16:24
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 16:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 16:25
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 4, Tool calls: 0
- Tokens: 10 in / 1.9K out [2.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 43s
- Log: OOMPAH-729__20260803T162427Z.jsonl
---
author: oompah
created: 2026-08-03 16:55
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 16:55
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-03 16:56
---
Understanding: the regression is an integrated same-head task whose failed terminal audit cannot be retried after operator-supplied gate evidence changes only audit evidence. I will trace the existing owner retry and evidence fingerprint paths, add a narrowly authenticated evidence-addendum rearm that preserves audit/ownership/SHA fencing and coalesces races, integrate it with the completion sweep, then cover the EXOCOMP-145 flow and rejection/idempotency cases.
---
author: oompah
created: 2026-08-03 16:58
---
Discovery:  currently only accepts completed records whose attempts are infrastructure/no-auditor/policy failures, and it has no current-fingerprint CAS or durable reason/addendum. The integrated sweep retries every integrated row in nonterminal states, so a completed same-fingerprint failure repeatedly returns  without a dedicated alert. I will add an owner-authenticated  contract requiring the current canonical fingerprint and successful named checks, persist a redacted rearm ledger, and make the sweep surface one idempotent recovery alert for the stale failure.
---
author: oompah
created: 2026-08-03 17:08
---
Implementation: extended the existing owner audit-retry path with a strict evidence-addendum mode. It requires the current canonical fingerprint, successful named checks, and a completed missing_evidence audit; supersedes only that failed record, preserves attempts, writes a redacted actor/reason/addendum rearm ledger, restores In Validation, and coalesces concurrent retries. The PATCH API and task CLI expose the documented contract, integrated fingerprint computation now uses the exact landed SHA consistently, and the integration sweep emits one idempotent owner-rearm alert instead of repeating already-completed warnings.
---
author: oompah
created: 2026-08-03 17:17
---
Verification: focused terminal coordinator/API/fingerprint/integration/CLI suites pass (393 tests), including same-head missing-evidence rearm followed by PASS to Done, non-owner/fingerprint/success-final rejection, coalescing, canonical integrated-SHA matching, and one-alert sweep recovery. The terminal mutation scan passes (6/6 allowlisted). Full direct pytest completed with 15,134 passed, 7 skipped, 1 xfailed, and one unrelated harness failure because the direct invocation did not set OOMPAH_PYTEST_RUN_ROOT for test_pytest_parallel.py; make test could not initialize its task-private uv scope due a host DBus kernel-thread error.
---
author: oompah
created: 2026-08-03 17:17
---
Implemented authenticated evidence-only terminal-audit rearm for unchanged integrated heads, with canonical integrated-SHA fencing, idempotent coordinator/API/CLI flow, sweep recovery alerting, operator docs, and regression coverage.
---
author: oompah
created: 2026-08-03 17:17
---
Completion: delivered and pushed the evidence-only terminal-audit recovery. Owners can rearm a same-integrated-SHA missing_evidence failure once with audit_retry_evidence_addendum; the coordinator preserves history and fencing, coalesces duplicates, and independent audit can PASS to Done. The sweep now exposes one actionable recovery alert and clears it after rearm. Focused 393-test suite and terminal mutation scan pass; full direct suite reached 15,134 passes with only the wrapper-env test failure documented above. Submitted for integration at the pushed head.
---
author: oompah
created: 2026-08-03 17:18
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 93
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 22m 27s
- Log: OOMPAH-729__20260803T165547Z.jsonl
---
author: oompah
created: 2026-08-03 17:54
---
Live delivery workaround: exact submitted head e4b2865e was stranded by the OOMPAH-732 standalone-authority race. Opened PR #686 against main after confirming the assigned worktree and remote branch are clean and exact. Existing verification evidence: 393 focused tests, terminal mutation scan, and 15,134-pass full direct suite; Makefile wrapper environment failure is documented above.
---
<!-- COMMENTS:END -->
