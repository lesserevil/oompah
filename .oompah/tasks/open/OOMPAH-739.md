---
id: OOMPAH-739
type: task
status: Open
priority: null
title: Preserve verified nested-epic Merged state when historical source branches
  are deleted
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T20:14:53.133307Z'
updated_at: '2026-08-03T21:27:43.762042Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e155d40e714fbb05b6b00b3e1e1e709c3faa7399e10d8bc0afcf73643352081c
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T21:27:35.863598+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Closest matches OOMPAH-165 and OOMPAH-162 are terminal\
    \ (Archived) and address earlier landing-detection cases, not this deleted-source-ref\
    \ regression. No active duplicate is confirmed.\nFocus handoff: duplicate_detector\
    \  \nDuplicate preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence:\
    \ Closest matches OOMPAH-165 and OOMPAH-162 are terminal (Archived) and address\
    \ earlier landing-detection cases, not this deleted-source-ref regression. No\
    \ active duplicate is confirmed."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d13f0692-ed59-4110-9eed-491052834ba6
oompah.task_costs:
  total_input_tokens: 47716
  total_output_tokens: 2555
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 47716
      output_tokens: 2555
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2284
    cost_usd: 0.0
    recorded_at: '2026-08-03T21:21:49.530609+00:00'
  - profile: default
    model: haiku
    input_tokens: 47706
    output_tokens: 271
    cost_usd: 0.0
    recorded_at: '2026-08-03T21:27:35.861628+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-739__20260803T211724Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-739
    source_sha: 576a85bfccedf903b9be03adb1088f1c69227c68
    completed_at: '2026-08-03T21:21:49.539449+00:00'
  - run_id: OOMPAH-739__20260803T212640Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-739
    source_sha: 576a85bfccedf903b9be03adb1088f1c69227c68
    completed_at: '2026-08-03T21:27:35.924669+00:00'
---
## Summary

Live regression after deploying OOMPAH-725 on 2026-08-03. During resume, terminal lifecycle enforcement demoted many historical shared/nested epic children from Merged to Done with 'parent epic ... could not be verified'. OOMPAH-587 and OOMPAH-588 are concrete false positives: both have durable PASS/Merged audits and reviewed merge commits into parent OOMPAH-584; OOMPAH-584 itself has a PASS/Merged audit proving PR #603 landed merge commit bb0fd760c3b2938d15ec2026ef5bfc2fd34b0682 on main. The parent source branch was normally deleted after merge. Nevertheless enforcement demoted the children, and ordinary reconciliation then resurrected OOMPAH-587 into In Validation and OOMPAH-588 into In Review, consuming reviews/auditors for already delivered work.\n\nImplementation scope:\n- Make shared/nested child Merged compatibility validation recognize durable parent landing evidence: recorded parent review/merge commit, terminal PASS/Merged audit, exact merge parents/ancestry, and configured target branch, even when the parent source branch was deleted normally.\n- Separate 'cannot currently fetch deleted source ref' from 'parent has not landed'; fail closed only when durable evidence is absent or contradictory.\n- Order startup/restart reconciliation so parent evidence is loaded before children are classified, or defer uncertain rows without mutating tracker state until verification completes.\n- Never demote a verified historical Merged task merely because caches, remote refs, or startup scans are temporarily incomplete.\n- Keep OOMPAH-725's intended repair for truly incompatible Merged children whose parent has not landed.\n- Avoid redispatching reviews/audits or reopening later shared-branch siblings as a consequence of a false demotion; preserve OOMPAH-447 ownership fencing.\n\nRelevant code: terminal_audit_enforcement legacy lifecycle reconciliation, shared-epic lifecycle validator and _epic_branch_landed_on_target, terminal audit/review evidence loading, startup ordering, and terminal/open-review reconciliation. Related tasks: OOMPAH-725, OOMPAH-726, OOMPAH-447.\n\nRequired tests:\n- Reproduce OOMPAH-584/587/588: nested child reviewed into parent, parent reviewed into main, both audits PASS/Merged, both source branches deleted; restart enforcement must retain all Merged states with zero new review/audit.\n- Cover merge-commit and fast-forward landing, patch-equivalent rebased parent head, deleted child and parent refs, stale/missing cache with authoritative forge evidence available, and transient forge failure.\n- Prove a genuinely unlanded parent still causes the OOMPAH-725 Merged-to-Done repair exactly once.\n- Prove a later open PR reusing the shared branch does not reopen unrelated siblings (OOMPAH-447 regression).\n- Run focused terminal enforcement, epic strategy, review ownership, deleted-branch recovery, startup/restart, and lifecycle suites plus make test.\n\nAcceptance criteria:\n- Verified nested epics such as OOMPAH-587 and OOMPAH-588 remain Merged across restart after normal branch deletion.\n- Uncertain verification never mutates terminal tracker state until authoritative evidence resolves.\n- Truly incompatible Merged children still converge safely to audited Done without losing history.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 21:17
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 21:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 21:21
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 4, Tool calls: 0
- Tokens: 10 in / 2.3K out [2.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 33s
- Log: OOMPAH-739__20260803T211724Z.jsonl
---
author: oompah
created: 2026-08-03 21:26
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 21:26
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 21:27
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 47.7K in / 271 out [48.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 26s
- Log: OOMPAH-739__20260803T212640Z.jsonl
---
<!-- COMMENTS:END -->
