---
id: OOMPAH-644
type: task
status: In Progress
priority: null
title: Make native task reads atomic across status-file moves
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T06:46:11.947079Z'
updated_at: '2026-07-31T07:12:01.354231Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
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
oompah.agent_run_id: 5684e061-ead7-43f8-bac4-4af641993d3c
oompah.task_costs:
  total_input_tokens: 162
  total_output_tokens: 5801
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 162
      output_tokens: 5801
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 162
    output_tokens: 5801
    cost_usd: 0.0
    recorded_at: '2026-07-31T06:49:10.710435+00:00'
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
<!-- COMMENTS:END -->
