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
updated_at: '2026-08-03T21:22:05.206169Z'
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
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: inconclusive\n\
    Matches: none\nEvidence: The supplied corpus contains only archived/terminal tasks.\
    \ OOMPAH-739 explicitly references OOMPAH-725, OOMPAH-726, and OOMPAH-447 as related\
    \ lifecycle and registry tasks, but all three are omitted from the 577 excluded\
    \ similarity candidates. Without access to these explicitly-referenced peer tasks'\
    \ full descriptions and active statuses, a confident duplicate determination is\
    \ impossible. The omitted-candidate budget prevents definitive comparison against\
    \ likely duplicate targets. Oompah should retry with a corpus that includes OOMPAH-725,\
    \ OOMPAH-726, OOMPAH-447, and other omitted candidates in the lifecycle/validation\
    \ domain.\n## Analysis\n\n**Examining OOMPAH-739 for Duplicates**\n\nTask OOMPAH-739\
    \ describes a regression after OOMPAH-725 where terminal lifecycle enforcement\
    \ incorrectly demotes nested epic children from Merged to Done when their parent\
    \ branch has been deleted, despite durable landing evidence (audit trails, merge\
    \ commits).\n\n**Corpus Status Review:**\n- Current task: OOMPAH-739 (Open - active)\n\
    - All other tasks in supplied corpus: Archived or Done (terminal states)\n- **No\
    \ active candidate tasks to evaluate**\n\n**Critical Limitation:**\nThe corpus\
    \ selection diagnostic shows:\n- Similarity candidates identified: 610\n- Candidates\
    \ included in corpus: 33\n- **Omitted candidates: 577**\n\nOOMPAH-739's description\
    \ explicitly references three related tasks:\n- OOMPAH-725 (the regression root\
    \ cause)\n- OOMPAH-726 (related lifecycle issue)\n- OOMPAH-447 (ownership fencing)\n\
    \n**None of these three are present in the supplied corpus** \u2014 they are among\
    \ the 577 omitted similarity candidates.\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: inconclusive\n\nMatches: none\n\nEvidence: The\
    \ supplied corpus contains only archived/terminal tasks. OOMPAH-739 explicitly\
    \ references OOMPAH-725, OOMPAH-726, and OOMPAH-447 as related lifecycle and registry\
    \ tasks, but all three are omitted from the 577 excluded similarity candidates.\
    \ Without access to these explicitly-referenced peer tasks' full descriptions\
    \ and active statuses, a confident duplicate determination is impossible. The\
    \ omitted-candidate budget prevents definitive comparison against likely duplicate\
    \ targets. Oompah should retry with a corpus that includes OOMPAH-725, OOMPAH-726,\
    \ OOMPAH-447, and other omitted candidates in the lifecycle/validation domain."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: '2026-08-03T21:22:49.536094+00:00'
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4f9f80a3-c467-42ac-93a4-19c3f4c7ebf3
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2284
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2284
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2284
    cost_usd: 0.0
    recorded_at: '2026-08-03T21:21:49.530609+00:00'
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
<!-- COMMENTS:END -->
