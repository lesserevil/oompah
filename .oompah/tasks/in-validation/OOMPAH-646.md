---
id: OOMPAH-646
type: task
status: In Validation
priority: null
title: Serialize review capacity across reconciliation sweeps and webhook lag
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T06:55:23.505409Z'
updated_at: '2026-07-31T08:33:11.033634Z'
work_branch: OOMPAH-646
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/613
review_number: '613'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8cea44fcdd02f4e924fa57935fdd74f9d999884b52f2399da3ce04e65229127f
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T06:58:02.245969+00:00'
  matched_identifiers: []
  evidence: "Based on my thorough investigation of the task tracker, I have completed\
    \ the duplicate investigation for OOMPAH-646.\n\n## Investigation Summary\n\n\
    I searched across all task states (open, backlog, merged, archived) for any existing\
    \ tasks that address:\n- Review capacity management across reconciliation sweeps\n\
    - Webhook timing and cache lag handling\n- The specific regression pattern where\
    \ max_in_flight_prs=1 constraint was violated\n- Durable reservation mechanisms\
    \ for review slots\n\n**Searches performed:**\n1. Direct search for related task\
    \ numbers (OOMPAH-598, OOMPAH-640, OOMPAH-642)\n2. Pattern searches: `review|reconciliation|webhook|capacity|max_in_flight|in_flight_prs`\n\
    3. Project-specific search for proj-14849f1b combined with review/reconciliation\
    \ terms\n4. Regex patterns combining reconciliation + review + sweep concepts\n\
    \n**Results:** \n- No existing open, backlog, or active tasks match OOMPAH-646's\
    \ scope\n- Existing project-related tasks (OOMPAH-272, OOMPAH-274, etc.) for proj-14849f1b\
    \ address merge conflicts and YOLO watchdog issues\u2014unrelated to review capacity\n\
    - The highest task ID currently in tracker is OOMPAH-282 (backlog), with OOMPAH-281\
    \ (open) being infrastructure-related (GitHub Actions runner)\n- OOMPAH-646 (ID\
    \ 646) is substantially newer than existing tasks with no prior equivalent\n\n\
    ---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Comprehensive search of .oompah/tasks across all\
    \ states found no existing active task addressing review capacity serialization\
    \ across reconciliation sweeps or webhook lag. The closest project-related tasks\
    \ (OOMPAH-272, OOMPAH-274, OOMPAH-281, OOMPAH-282) address unrelated concerns\
    \ (merge conflicts, CI runners, state branch migration). This is a genuinely new\
    \ issue describing a regression where max_in_flight_prs constraints were violated\
    \ across successive sweeps\u2014a problem not previously tracked in the system."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 6edd4783-09ce-4404-a4f4-cdb87979de7b
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-646__20260731T065633Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-646
    source_sha: d7027de514d1fcee1cf3e150f9f02b11b3168071
    completed_at: '2026-07-31T06:58:02.250282+00:00'
oompah.task_costs:
  total_input_tokens: 40853359
  total_output_tokens: 75206
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 40853359
      output_tokens: 75206
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 146
    output_tokens: 4804
    cost_usd: 0.0
    recorded_at: '2026-07-31T06:58:02.245280+00:00'
  - profile: default
    model: haiku
    input_tokens: 40853213
    output_tokens: 70402
    cost_usd: 0.0
    recorded_at: '2026-07-31T08:02:29.518164+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-646
  head_sha: 355258ef0d1b1600f09cd111511f2828946e4ec7
  submitted_at: '2026-07-31T08:02:14.140071+00:00'
  updated_at: '2026-07-31T08:02:14.140071+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/613
oompah.review_number: '613'
oompah.work_branch: OOMPAH-646
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-179ca730d57d
    project_id: proj-14849f1b
    task_id: OOMPAH-646
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4e48fb1840632749f46204f76957903b9651e77b6cd3ec64a9f92abe38fa76f4
    attempts:
    - version: 1
      attempt_id: attempt-e672336e007e
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 4e48fb1840632749f46204f76957903b9651e77b6cd3ec64a9f92abe38fa76f4
      created_at: '2026-07-31T08:33:05.500595+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T08:33:05.500595+00:00'
      branch_key: OOMPAH-646
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T08:19:02.154963+00:00'
    updated_at: '2026-07-31T08:33:05.500595+00:00'
  - version: 1
    audit_id: audit-6514bbb96a7e
    project_id: proj-14849f1b
    task_id: OOMPAH-646
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4e48fb1840632749f46204f76957903b9651e77b6cd3ec64a9f92abe38fa76f4
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T08:19:02.154963+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-e672336e007e
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4e48fb1840632749f46204f76957903b9651e77b6cd3ec64a9f92abe38fa76f4
    created_at: '2026-07-31T08:33:05.500595+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T08:33:05.500595+00:00'
    branch_key: OOMPAH-646
---
## Summary

Live regression on 2026-07-31: project proj-14849f1b has max_in_flight_prs=1. PR #608 for OOMPAH-640 remained OPEN, CLEAN, and fully green while a later standalone Ready reconciliation created PR #609 for OOMPAH-642 at 06:53:54. OOMPAH-598 fixed same-sweep local reservation, but review capacity was again exceeded across successive sweeps/cache or webhook timing. Implementation scope: make review-slot acquisition authoritative and durable across reconciliation sweeps, concurrent webhook/review refreshes, branch-gate completions, and process restart. Acquire a per-project compare-and-swap lease/reservation before review creation, count existing open forge reviews plus durable unexpired reservations, commit the reservation to the created review identity, and release it on merge/close/create failure. Stale cached review data must never permit a second review when the forge still reports an open one. Preserve retryability for deferred Ready tasks and avoid false stranded-delivery alerts. Relevant files include standalone Ready reconciliation, _project_review_capacity/_count_open_reviews, review cache/webhook updates, review creation, and persisted delivery/review state. Required tests: deterministic later-sweep reproduction with stale cache after first PR creation; concurrent reconciliation and webhook timing; existing green-but-not-yet-merged PR; create failure; restart with reservation; merge/close releases slot; two projects remain isolated. Acceptance: with max_in_flight_prs=1 exactly one of two Ready branches owns an open PR until that PR is actually closed or merged, focused delivery/review tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 06:56
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 06:56
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 06:58
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 51, Tool calls: 25
- Tokens: 146 in / 4.8K out [5.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 41s
- Log: OOMPAH-646__20260731T065633Z.jsonl
---
author: oompah
created: 2026-07-31 06:58
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 06:58
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-31 07:02
---
Additional live consequence: PR #610 for OOMPAH-643 was created from base d7027de514 while overlapping PR #609 remained open. When #609 merged as 50625abed, #610 immediately became DIRTY/CONFLICTING at head 84521c288. The capacity race therefore creates avoidable rebase work and delays the critical terminal-audit metrics fix; include this cross-sweep stale-base sequence in the deterministic regression.
---
author: oompah
created: 2026-07-31 08:02
---
Implementation pushed at 355258ef0 (includes d06656a56). Durable SQLite review reservations serialize capacity across sweeps/processes, reconcile forge state, release on close/merge/failure, and preserve retryability. Coordination review: OOMPAH-642 and OOMPAH-643 are already in this branch ancestry; OOMPAH-621 is integrated into its parent branch and has no unresolved overlap here. Verification: focused capacity/webhook/standalone/epic/close-gate coverage 229 passed; ACP handoff recovery 8 passed with OOMPAH_AGENT_LOG_DIR redirected writable; terminal mutation scan passed. The initial full run had 14,196 passed and 12 environment/mock-compatibility failures; all 12 were rerun and passed after the review-state normalization fix.
---
author: oompah
created: 2026-07-31 08:02
---
Pushed durable review-capacity serialization and compatibility normalization in 355258ef0. Focused regressions, ACP handoff recovery, and terminal mutation scan pass; task submitted for validation.
---
author: oompah
created: 2026-07-31 08:02
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 282
- Tokens: 40.9M in / 70.4K out [40.9M total]
- Cost: $0.0000
- Exit: terminated, Duration: 1h 4m 13s
- Log: OOMPAH-646__20260731T065821Z.jsonl
---
author: oompah
created: 2026-07-31 08:11
---
Branch quality gate passed for `355258ef0d1b1600f09cd111511f2828946e4ec7` using `make test` in 410.1s. Review creation may proceed.
---
author: oompah
created: 2026-07-31 08:19
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 08:19
---
YOLO: merged PR #613.
---
author: oompah
created: 2026-07-31 08:33
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 08:33
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
