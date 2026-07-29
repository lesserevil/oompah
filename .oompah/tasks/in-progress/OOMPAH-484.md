---
id: OOMPAH-484
type: feature
status: In Progress
priority: 1
title: Expose safe terminal-audit state in project, task, and activity APIs
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-483
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:08:23.210919Z'
updated_at: '2026-07-29T18:26:06.985098Z'
work_branch: epic-OOMPAH-460--task-OOMPAH-484
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b97e7d30daa63f7aedc6e2c4faf2a97a83d5897fe6d749753c1ffb151349ccb4
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T02:02:37.417127+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Reviewed all active task records. OOMPAH-281 concerns self-hosted CI
    runners; OOMPAH-282 concerns state-branch migration. Archived OOMPAH-214 mentions
    release-delivery audit state but is terminal and covers a different scope.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 869e3c82-3b1d-49e1-8b54-42642e4cb8f7
oompah.work_branch: epic-OOMPAH-460--task-OOMPAH-484
oompah.task_costs:
  total_input_tokens: 391727
  total_output_tokens: 1848
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 391727
      output_tokens: 1848
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 391727
    output_tokens: 1848
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:02:37.416064+00:00'
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-460--task-OOMPAH-484
  base_branch: epic-OOMPAH-460
  base_sha: b0ceda2643cbc37c166ac58bed9a9b6f3898b681
  updated_at: '2026-07-29T18:26:04.847814+00:00'
---
## Summary

Implementation scope

Add a safe audit summary to task list/detail responses, project status, running/retrying agent snapshots, and the activity endpoint. Include requested terminal target, queue/running/result phase, attempt count, evidence fingerprint prefix and source/target SHAs, safe contributor/auditor provider-model identities, latest verdict/classification/summary, timestamps, and owner override flag. Never expose credentials, prompts, full diffs, hidden tracker metadata, or untrusted model output. Keep legacy fields unchanged and omit/null the summary for grandfathered or never-audited tasks.

Tests

Add API serialization/redaction tests for queued, running, passed, failed, overridden, grandfathered, malformed metadata, and ACP unknown model records. Verify list/detail/activity agree and existing API consumers remain compatible. Run focused tests and make test.

Acceptance criteria

UI and operators can understand audit state from stable safe APIs without parsing comments or tracker metadata, and no sensitive content is exposed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 02:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 02:02
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 7
- Tokens: 391.7K in / 1.8K out [393.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 53s
- Log: OOMPAH-484__20260729T020148Z.jsonl
---
author: oompah
created: 2026-07-29 18:25
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 18:26
---
Focus: Frontend Developer
---
<!-- COMMENTS:END -->
