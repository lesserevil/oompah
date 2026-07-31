---
id: OOMPAH-644
type: task
status: Merged
priority: null
title: Make native task reads atomic across status-file moves
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T06:46:11.947079Z'
updated_at: '2026-07-31T18:17:28.717721Z'
work_branch: OOMPAH-644
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/611
review_number: '611'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1bb676715f409182ac83e05ff8bfffa52da5656fb7b87cab02dc40fc1e0c7c2a
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T06:49:10.711646+00:00'
  matched_identifiers: []
  evidence: "Based on my thorough investigation of the task repository, I have completed\
    \ the duplicate screening for OOMPAH-644.\n\n## Duplicate Screening Summary\n\n\
    I searched across all task states (open, backlog, merged, archived) using multiple\
    \ keyword patterns related to:\n- Reader-writer races on status files\n- Atomic\
    \ status transitions and file moves  \n- ENOENT errors during task reads\n- Path\
    \ enumeration followed by file open races\n- Task corruption diagnostics\n- Concurrent\
    \ fetch operations\n\n**Comprehensive search results:**\n- All `.oompah/tasks/`\
    \ directories (200+ tasks scanned)\n- `docs/` and `plans/` directories\n- Regex\
    \ patterns: native tracker, race, concurrent, ENOENT, atomic, status move, fetch_all,\
    \ fetch_issue, corrupt, dispatch, scheduler\n- Specific references to OOMPAH-621\
    \ and OOMPAH-641 mentioned in the issue\n\n**Closest candidate reviewed:**\n-\
    \ `plans/concurrent-git-tracker-writes.md` references OOMPAH-267 and OOMPAH-268,\
    \ which describe a race condition between two OompahMdTracker instances racing\
    \ to commit via git. However, that issue is about git commit atomicity when two\
    \ tracker instances acquire separate write locks during graceful reload\u2014\
    a different problem layer than OOMPAH-644. OOMPAH-267/268 are about git subprocess\
    \ serialization; OOMPAH-644 is about reader-writer races on filesystem path enumeration\
    \ + file open operations across status directory moves.\n\n**Active tasks reviewed:**\n\
    - OOMPAH-281 (Open): Self-hosted GitHub Actions runner setup\n- OOMPAH-282 (Backlog):\
    \ State branch migration error\n\nNeither is related to native tracker read atomicity\
    \ or status-file move races.\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\
    \ Comprehensive search of all task states, docs, and plans found no existing active\
    \ task describing the same reader-writer race condition where a concurrent reader\
    \ enumerates an old status directory path, then receives ENOENT when a writer\
    \ atomically moves the task file to"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: ba4c6d0b-dcb0-4b53-be1a-00516ceb6a08
oompah.task_costs:
  total_input_tokens: 195
  total_output_tokens: 6920
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 162
      output_tokens: 5801
      cost_usd: 0.0
    unknown:
      input_tokens: 33
      output_tokens: 1119
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 162
    output_tokens: 5801
    cost_usd: 0.0
    recorded_at: '2026-07-31T06:49:10.710435+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 33
    output_tokens: 1119
    cost_usd: 0.0
    recorded_at: '2026-07-31T08:11:08.284937+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-644__20260731T064652Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-644
    source_sha: 6a8d6e9fbb53e12dc4739e89a0eabf56c6ad25f5
    completed_at: '2026-07-31T06:49:10.721264+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-644
  head_sha: ab4cab20c0697076098bd429d529fd3d8d3434e9
  submitted_at: '2026-07-31T07:21:58.711048+00:00'
  updated_at: '2026-07-31T07:21:58.711048+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/611
oompah.review_number: '611'
oompah.work_branch: OOMPAH-644
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    no-auditor-audit-710535de2bba-2: '2026-07-31T08:54:27.004450+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-b9bd25c5c20a
    project_id: proj-14849f1b
    task_id: OOMPAH-644
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0df6c64231ea0cc330c24b6722280e8d3de176fedcf80a8d9a7680a38727410b
    authorized_by:
      version: 1
      identity: lesserevil
      source: api
    reason: 'PR #611 is merged; exact branch quality gate passed on ab4cab20c0697076098bd429d529fd3d8d3434e9;
      both configured independent auditor candidates (opus and sonnet) were attempted
      and exhausted. Operator reviewed the recorded evidence and is clearing the infeasible
      audit deadlock.'
    created_at: '2026-07-31T08:55:16.942016+00:00'
  - version: 1
    override_id: override-0a4d0cb316f1
    project_id: proj-14849f1b
    task_id: OOMPAH-644
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a81c4c36325d4f4720adcfab95e9468745bbc8a9b18d42ba39a23726310c0601
    authorized_by:
      version: 1
      identity: lesserevil
      source: api
    reason: PR 611 merged exact head ab4cab20c0697076098bd429d529fd3d8d3434e9 as fa26c40007ce128012cf76d93334cba51181709f.
      This owner restage preserves the existing Merged lifecycle outcome while binding
      it to current evidence and retiring the obsolete pre-fix no-independent-candidate
      alert audit-710535de2bba.
    created_at: '2026-07-31T18:17:24.314056+00:00'
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-710535de2bba
    project_id: proj-14849f1b
    task_id: OOMPAH-644
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0df6c64231ea0cc330c24b6722280e8d3de176fedcf80a8d9a7680a38727410b
    attempts:
    - version: 1
      attempt_id: attempt-ab69e882ab0d
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0df6c64231ea0cc330c24b6722280e8d3de176fedcf80a8d9a7680a38727410b
      created_at: '2026-07-31T08:03:43.599075+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T08:03:43.599075+00:00'
      branch_key: OOMPAH-644
      ended_at: '2026-07-31T08:33:02.134755+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-e83d7b208648
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0df6c64231ea0cc330c24b6722280e8d3de176fedcf80a8d9a7680a38727410b
      created_at: '2026-07-31T08:33:03.261699+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-07-31T08:33:03.261699+00:00'
      branch_key: OOMPAH-644
      candidate_rotation_count: 1
      ended_at: '2026-07-31T08:54:25.880928+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: no-auditor-audit-710535de2bba-2
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0df6c64231ea0cc330c24b6722280e8d3de176fedcf80a8d9a7680a38727410b
      verdict: fail
      failure_classification: no_auditor
      created_at: '2026-07-31T08:54:27.004284+00:00'
      completed_at: '2026-07-31T08:54:27.004284+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T07:38:09.160039+00:00'
    updated_at: '2026-07-31T08:54:27.004284+00:00'
  - version: 1
    audit_id: audit-68272593d90a
    project_id: proj-14849f1b
    task_id: OOMPAH-644
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0df6c64231ea0cc330c24b6722280e8d3de176fedcf80a8d9a7680a38727410b
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T07:38:09.160039+00:00'
  - version: 1
    audit_id: audit-2117ba0c1103
    project_id: proj-14849f1b
    task_id: OOMPAH-644
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a81c4c36325d4f4720adcfab95e9468745bbc8a9b18d42ba39a23726310c0601
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: api
    previous_state: Merged
    created_at: '2026-07-31T18:16:55.443513+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-ab69e882ab0d
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0df6c64231ea0cc330c24b6722280e8d3de176fedcf80a8d9a7680a38727410b
    created_at: '2026-07-31T08:03:43.599075+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T08:03:43.599075+00:00'
    branch_key: OOMPAH-644
    ended_at: '2026-07-31T08:33:02.134755+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-e83d7b208648
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0df6c64231ea0cc330c24b6722280e8d3de176fedcf80a8d9a7680a38727410b
    created_at: '2026-07-31T08:33:03.261699+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-07-31T08:33:03.261699+00:00'
    branch_key: OOMPAH-644
    candidate_rotation_count: 1
    ended_at: '2026-07-31T08:54:25.880928+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
---
## Summary

Live scheduler evidence on 2026-07-31 reproduced a native Markdown tracker race twice: while OOMPAH-621 moved through Open/Ready at 06:03 and OOMPAH-641 moved through Ready at 06:34, a concurrent reader enumerated the old status path and then received ENOENT opening .oompah/tasks/<old-status>/<task>.md. The tracker logged the valid task as corrupt and stated that dispatch would be suppressed, even though the file already existed at its new canonical status path and the task later recovered.

Implementation scope: make OompahMdTracker reads consistent with concurrent CLI/server status transitions and state-branch commits. A fetch that observes ENOENT after enumeration must distinguish an atomic status-file move from true disappearance/corruption, refresh the task index or resolve the identifier across canonical status directories under the tracker write/read synchronization boundary, and retry against one authoritative state-branch generation. Do not restore files by hand or weaken true malformed/missing-file detection. Review fetch_all_issues/fetch_issue_detail path caching, status update rename/commit ordering, state-worktree locking, and scheduler corruption diagnostics.

Required tests: deterministic barrier between path enumeration and file open while another writer moves Open to Ready and Ready to In Progress; concurrent comment plus status update; repeated rapid status changes; state-branch refresh/commit generation change; deleted or malformed file remains an actionable corruption error; multi-process or separate tracker-instance reproduction if production uses separate instances. Acceptance: no transient ENOENT/corrupt warning or dispatch suppression for an intact moved task, readers return either the pre-move or post-move coherent record, true corruption still fails closed, focused native-tracker concurrency tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 06:46
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 06:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 06:49
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 59, Tool calls: 32
- Tokens: 162 in / 5.8K out [6.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 20s
- Log: OOMPAH-644__20260731T064652Z.jsonl
---
author: oompah
created: 2026-07-31 06:49
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 06:49
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-31 07:12
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 56
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 22m 37s
- Log: OOMPAH-644__20260731T064926Z.jsonl
---
author: oompah
created: 2026-07-31 07:12
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-31 07:12
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-31 07:22
---
Atomic native task reads across status moves
---
author: oompah
created: 2026-07-31 07:22
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 0, Tool calls: 62
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 10m 14s
- Log: OOMPAH-644__20260731T071232Z.jsonl
---
author: oompah
created: 2026-07-31 07:30
---
Branch quality gate passed for `ab4cab20c0697076098bd429d529fd3d8d3434e9` using `make test` in 272.8s. Review creation may proceed.
---
author: oompah
created: 2026-07-31 07:38
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 07:38
---
YOLO: merged PR #611.
---
author: oompah
created: 2026-07-31 08:03
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 08:03
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 08:11
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 20
- Tokens: 33 in / 1.1K out [1.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 24s
- Log: OOMPAH-644__20260731T080348Z.jsonl
---
author: oompah
created: 2026-07-31 08:33
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-07-31 08:33
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 08:54
---
Needs Human — Done audit requires operator input.

No independent auditor candidate is available for this audit (All eligible auditor candidates were already attempted for this audit.). Configure the `auditor` role with at least one healthy provider/model that is independent of the task contributors, then move the task back to Open to retry.
---
author: oompah
created: 2026-07-31 08:55
---
Override by lesserevil: terminal transition to Merged applied by project owner.

Reason: PR #611 is merged; exact branch quality gate passed on ab4cab20c0697076098bd429d529fd3d8d3434e9; both configured independent auditor candidates (opus and sonnet) were attempted and exhausted. Operator reviewed the recorded evidence and is clearing the infeasible audit deadlock.
---
author: oompah
created: 2026-07-31 18:17
---
Override by lesserevil: terminal transition to Merged applied by project owner.

Reason: PR 611 merged exact head ab4cab20c0697076098bd429d529fd3d8d3434e9 as fa26c40007ce128012cf76d93334cba51181709f. This owner restage preserves the existing Merged lifecycle outcome while binding it to current evidence and retiring the obsolete pre-fix no-independent-candidate alert audit-710535de2bba.
---
<!-- COMMENTS:END -->
