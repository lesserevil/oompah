---
id: OOMPAH-645
type: task
status: In Progress
priority: null
title: Clear recovered terminal-audit transport failures without contaminating later
  audits
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T06:47:58.732088Z'
updated_at: '2026-07-31T07:14:21.761168Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f4416679eb9e4638e32ed608869ac730e290b5104a858835ed90572897c53054
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T06:51:24.951133+00:00'
  matched_identifiers: []
  evidence: 'Based on my comprehensive investigation, I can now provide my findings.


    ## Investigation Summary


    I performed an exhaustive search for existing tasks that might cover the same
    issue as OOMPAH-645:


    **Searches Performed:**

    1. Scanned all `.oompah/tasks/` directories (open, backlog, merged, archived)

    2. Searched for keywords: `terminal`, `audit`, `health`, `alert`, `failure`, `degradation`,
    `recovery`, `transport`, `contamination`, `stale`

    3. Searched for the referenced task IDs from the issue: OOMPAH-592, OOMPAH-607,
    OOMPAH-641

    4. Scanned documentation in `docs/` and `plans/` directories

    5. Cross-referenced the highest numbered existing tasks (OOMPAH-282 is the highest
    in backlog; OOMPAH-280 is the highest merged)


    **Key Findings:**


    1. **No existing task** covers the issue described in OOMPAH-645 (terminal audit
    health alerts persisting after recovery, contaminating subsequent unrelated audits)


    2. **Most recent activity**: OOMPAH-281 and OOMPAH-282 from July 20-22, 2026;
    this issue is dated July 31, 2026 (today)


    3. **Task numbering gap**: Highest existing task is OOMPAH-282; OOMPAH-645 is
    being created as a new task


    4. **Code exists but bug is new**: The file `oompah/terminal_audit_health.py`
    exists and is referenced as the target for fixes, confirming this is infrastructure
    work, not a duplicate of prior design discussions


    5. **Closest reviewed tasks** (all unrelated to this issue): OOMPAH-281 (GitHub
    Actions runner), OOMPAH-282 (Unicode encoding bug), OOMPAH-279/280 (epic branch
    rebasing)


    ---


    **Focus handoff: duplicate_detector**


    **Duplicate preflight verdict: no_duplicate**


    **Matches: none**


    **Evidence:** Comprehensive search of 280+ tasks across all states (open, backlog,
    merged, archived) found no existing task addressing terminal audit health alert
    clearing after recovery or stale failure contamination between audits. The issue
    references live reproduction tasks (OOMPAH-607, 641, 592) from a managed project
    that exposed this bug in oompah''s infrastru'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 8d982144-3fab-4d82-abc0-26d163554ed1
oompah.task_costs:
  total_input_tokens: 154
  total_output_tokens: 6782
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 154
      output_tokens: 6782
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 154
    output_tokens: 6782
    cost_usd: 0.0
    recorded_at: '2026-07-31T06:51:24.949997+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-645__20260731T064937Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-645
    source_sha: 1dc3f53e52b5d8ef704e16355d4cb0bb87379689
    completed_at: '2026-07-31T06:51:24.959976+00:00'
---
## Summary

Live reproduction on 2026-07-31: OOMPAH-607 auditor attempt 1 ended with a transport failure at the configured turn limit, attempt 2 launched successfully and completed the terminal transition, and OOMPAH-607 left In Validation. The terminal_audit_health:launch_failures error nevertheless remained degraded with transport_failure_count=1 and text claiming failures for pending audits. When OOMPAH-641 subsequently entered validation, the stale OOMPAH-607 failure appeared to describe the unrelated new audit. This violates OOMPAH-592 acceptance that alerts clear after underlying recovery.

Implementation scope: model launch/transport failures as unresolved per-audit attempt health, not a process-lifetime historical error gauge. A successful replacement launch may keep diagnostic history but must establish active recovery; a successful verdict/terminal transition must resolve the prior failure and clear the actionable alert. A later unrelated pending audit must never inherit another task’s failure. Preserve durable alerts for genuinely unresolved retries, repeated transport failures, retry exhaustion, unavailable transports, and restart recovery. Relevant files: oompah/terminal_audit_health.py, terminal audit coordinator/orchestrator observation construction, persisted attempt metadata, state/alerts serialization, and dashboard tests.

Required tests: transport failure then successful retry/verdict clears degradation; active replacement is represented as recovering rather than requiring operator transport restoration; one recovered audit plus a different pending audit stays clean; restart between failure/retry/success; repeated failure and retry exhaustion remain actionable; multi-project isolation; alert text/counts refer only to unresolved audit identities. Acceptance: after OOMPAH-607-style recovery the health alert disappears, later audits are not contaminated, historical counters remain observable separately from actionable health, focused terminal-audit health tests pass, terminal mutation scan passes, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 06:49
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 06:49
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 06:51
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 61, Tool calls: 27
- Tokens: 154 in / 6.8K out [6.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 56s
- Log: OOMPAH-645__20260731T064937Z.jsonl
---
author: oompah
created: 2026-07-31 06:51
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 06:51
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-31 07:13
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 81
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 22m 6s
- Log: OOMPAH-645__20260731T065139Z.jsonl
---
author: oompah
created: 2026-07-31 07:14
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-31 07:14
---
Focus: Frontend Developer
---
<!-- COMMENTS:END -->
