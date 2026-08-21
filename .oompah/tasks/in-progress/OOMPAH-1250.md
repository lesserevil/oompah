---
id: OOMPAH-1250
type: task
status: In Progress
priority: null
title: Restore GitLab external issue intake for native Markdown projects
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- needs:feature
assignee: null
created_at: '2026-08-13T16:21:54.348846Z'
updated_at: '2026-08-21T07:01:39.397860Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: b14bdf4d-7f07-48e7-bea5-bd9a4c15a754
  request_fingerprint: 35c587882c8a948f1f7683918040d652db1c9e5eb82d33f59e8351c7a160037b
oompah.lifecycle_revision: 2
oompah.last_batch:
  batch_id: batch-41327bd44d2248989351b0a98c84746f
  actor: shedwards
  committed_at: '2026-08-18T16:18:18.970327Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2517f579a77ef9ddf988d97408ecf08e7492118dc7bd2c3fadd51d0dbd586a34
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T01:55:54.246108+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1250 describes unique functionality for implementing\
    \ GitLab external issue intake with provider-qualified metadata and forge-neutral\
    \ bridge design. The 25 included similarity candidates are entirely focused on\
    \ internal workflow management, terminal audits, and epic handling\u2014completely\
    \ disjoint from external integration work. The referenced OOMPAH-324 is archived\
    \ and cannot serve as an active duplicate target. No active task in the corpus\
    \ overlaps with external issue import requirements.\nLooking at OOMPAH-1250, I\
    \ need to determine whether this is a duplicate of an existing active task.\n\n\
    ## Analysis\n\n**OOMPAH-1250 Scope:**\nThe task is to restore GitLab external\
    \ issue intake for native Markdown projects by:\n- Implementing a forge-neutral\
    \ external-intake bridge\n- Adding GitLab issue/comment import capabilities  \n\
    - Creating provider-qualified `oompah.external.gitlab` metadata\n- Implementing\
    \ idempotency, terminal status handling, and GitLab webhook routing\n- Adding\
    \ polling recovery\n- Preserving GitHub behavior through compatibility wrappers\n\
    \nThe description explicitly references \"Revive the unlanded scope of archived\
    \ OOMPAH-324.\"\n\n**Corpus Review:**\nI've examined the 25 similarity candidates\
    \ included in the provided task corpus. These are all focused on:\n- Terminal\
    \ audit lifecycle and quality gates (OOMPAH-1000 through OOMPAH-1083)\n- Workflow\
    \ runtime, epic management, and scheduler issues\n- Internal workflow/job handling\
    \ and state management\n\nNone of these tasks address:\n- External issue intake\
    \ or bridges\n- GitLab integration\n- GitHub/GitLab forge-neutral implementations\n\
    - Issue/comment import mechanisms\n\n**Key Observations:**\n1. OOMPAH-324 is referenced\
    \ as the archived predecessor but is in a terminal state (Archived) and therefore\
    \ cannot be a valid duplicate target per the screening rules\n2. No active (Open/In\
    \ Progress/Ready to Integrate) task in the corpus matches OOMPAH-1250's scope\
    \ of external GitLab issue intake\n3. The 433 omitted similarity candidates may\
    \ have archived or lower-scoring matches, but the included candidates show no\
    \ overlap with external intake functionality\n4. The task blocks TRICKLE-132,\
    \ indicating it's new work, not rework of an existing open issue\n\n---\n\nFocus\
    \ handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\n\
    Matches: none\n\nEvidence: OOMPAH-1250 describes unique functionality for implementing\
    \ GitLab external issue intake with provider-qualified metadata and forge-neutral\
    \ bridge design. The 25 included similar"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4128c5ff-3ec1-464f-a158-4b2fa7e6efab
oompah.work_contributors:
  runs:
  - run_id: c39b31ff527f433f8499e69b01c975f0--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1250
    source_sha: null
    completed_at: ''
  - run_id: 75b28ab140cc4ff7947b6a1aa791a00d--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1250
    source_sha: null
    completed_at: ''
  - run_id: 75b28ab140cc4ff7947b6a1aa791a00d--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1250
    source_sha: null
    completed_at: ''
  - run_id: ad70db683e60460dae5730c7e1b91629--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1250
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T01:55:54.249406+00:00'
  - run_id: bae9008df3dd4b47a1cdcd14bbb182a8--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: docs
    source_branch: OOMPAH-1250
    source_sha: null
    completed_at: ''
  - run_id: 09f42f85dab842349107a46335011116--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: docs
    source_branch: OOMPAH-1250
    source_sha: null
    completed_at: ''
  - run_id: 08686c9350a043838f41a286f2e9f070--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: docs
    source_branch: OOMPAH-1250
    source_sha: null
    completed_at: ''
  - run_id: f843f772524542449b97eea65adf3ae8--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: docs
    source_branch: OOMPAH-1250
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1621
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1621
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1621
    cost_usd: 0.0
    recorded_at: '2026-08-21T01:55:54.245250+00:00'
---
## Summary

Revive the unlanded scope of archived OOMPAH-324. The current server parses and authenticates GitLab Issue/Note hooks and has GitLabIssueTracker, but github_intake_bridge.py, poll_github_issue_intake_project(), and server routing still import only GitHub issues events. Implement a forge-neutral native external-intake bridge with GitLab issue/comment import, provider-qualified oompah.external.gitlab metadata, idempotency, terminal status comment/closure, untrusted provenance, GitLab webhook routing, and polling recovery. Preserve GitHub behavior through compatibility wrappers. Acceptance: an oompah_md GitLab project imports a complete issue into Proposed, copies human comments once, archives on external close, mirrors Merged/Archived to GitLab, handles missed webhook state via poll, and passes GitHub plus GitLab regression tests. This blocks Trickle TRICKLE-132.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 23:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:03
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:04
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 55s
- Log: OOMPAH-1250__20260820T230356Z.jsonl
---
author: oompah
created: 2026-08-21 00:19
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 00:20
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 49s
---
author: oompah
created: 2026-08-21 01:54
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 01:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 01:55
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 56s
- Log: OOMPAH-1250__20260821T015520Z.jsonl
---
author: oompah
created: 2026-08-21 05:22
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 05:22
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-21 05:23
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 6s
- Log: OOMPAH-1250__20260821T052258Z.jsonl
---
author: oompah
created: 2026-08-21 05:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 05:45
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-21 05:45
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 15s
- Log: OOMPAH-1250__20260821T054515Z.jsonl
---
author: oompah
created: 2026-08-21 06:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 06:12
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-21 06:12
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 35s
- Log: OOMPAH-1250__20260821T061219Z.jsonl
---
author: oompah
created: 2026-08-21 06:49
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 06:49
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 8s
---
author: oompah
created: 2026-08-21 06:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 07:00
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-21 07:01
---
HANDOFF: This task requires backend implementation of GitLab external issue intake (code changes to github_intake_bridge.py, server routing, polling logic, metadata structures, etc.). As a Technical Writer, I cannot implement feature code. This task needs a backend or feature specialist to: (1) implement the forge-neutral external-intake bridge, (2) add GitLab issue/comment import, (3) implement idempotency and webhook routing, (4) add polling recovery. Recommend next focus: backend developer or feature engineer.
---
<!-- COMMENTS:END -->
