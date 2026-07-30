---
id: OOMPAH-594
type: feature
status: In Progress
priority: 1
title: Reload HTTP Basic credentials safely after htpasswd rotation
parent: OOMPAH-586
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:55.490677Z'
updated_at: '2026-07-30T15:29:27.168609Z'
work_branch: epic-OOMPAH-586--task-OOMPAH-594
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a5877e72c28f883709890b87c9b5e3bd5e5a3cefcb7907fbaf7997fec50b6aa5
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T15:28:34.778081+00:00'
  matched_identifiers: []
  evidence: "Based on my thorough search of the oompah task tracker, I have completed\
    \ the duplicate investigation for OOMPAH-594. Here are my findings:\n\n## Search\
    \ Conducted\n\nI searched across all task states (.oompah/tasks):\n- **Open**:\
    \ Only OOMPAH-281 found (GitHub Actions runner setup, unrelated)\n- **Merged**:\
    \ OOMPAH-271, OOMPAH-272, OOMPAH-275, OOMPAH-277, OOMPAH-278, OOMPAH-279, OOMPAH-280\
    \ (all rebasing tasks for epic-OOMPAH-253, unrelated)\n- **Backlog**: OOMPAH-282\
    \ (state branch migration error, unrelated)\n- **Archived**: 260+ archived tasks\
    \ searched with patterns for: `htpasswd`, `HTTP.*[Bb]asic`, `credential.*rotat`,\
    \ `http_auth`, `auth.*reload`, `Basic.*auth`, `reload`, `rotat`, `htpasswd` \u2014\
    \ no matches\n\nI also searched documentation in `docs/`, `plans/`, `README.md`,\
    \ and `WORKFLOW.md` for HTTP auth, htpasswd, and credential-related content \u2014\
    \ no matches found.\n\n## Analysis\n\nOOMPAH-594 addresses: \"Reload HTTP Basic\
    \ credentials safely after htpasswd rotation\" with scope covering file identity\
    \ detection, atomic loading, parse/read failure handling, redacted status exposure,\
    \ and auth middleware integration.\n\nNo existing open, merged, or active task\
    \ covers this specific scope:\n- No HTTP Basic authentication reload feature exists\n\
    - No htpasswd rotation handling has been implemented\n- The epic parent (OOMPAH-586)\
    \ and siblings (OOMPAH-593, OOMPAH-595) are not in the tracked task folder (consistent\
    \ with the coordination comment indicating this is a fresh epic)\n\nThis is a\
    \ **new feature task**, not a duplicate of prior work.\n\n---\n\n**Focus handoff:\
    \ duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\n**Matches:\
    \ none**\n\n**Evidence:** Comprehensive search across all task tracker states\
    \ (open, merged, backlog, archived) using keywords for HTTP Basic authentication,\
    \ htpasswd, credential rotation, and reload functionality returned zero matches.\
    \ The closest tracked work is rebasing tasks for epic-OOMPAH-253 (state-branch\
    \ infrastructure), which is orthogonal to OOMPAH-594's H"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
oompah.agent_run_id: 977c8566-2ca5-47b0-b0b3-84b9d3a99feb
oompah.work_branch: epic-OOMPAH-586--task-OOMPAH-594
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-586--task-OOMPAH-594
  base_branch: epic-OOMPAH-586
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T15:28:47.725225+00:00'
oompah.task_costs:
  total_input_tokens: 46270
  total_output_tokens: 5787
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46270
      output_tokens: 5787
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 972
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:22:31.000460+00:00'
  - profile: default
    model: haiku
    input_tokens: 146
    output_tokens: 4361
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:28:34.777046+00:00'
  - profile: default
    model: haiku
    input_tokens: 46114
    output_tokens: 454
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:29:23.206083+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-594__20260730T152001Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-586--task-OOMPAH-594
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:22:31.011857+00:00'
  - run_id: OOMPAH-594__20260730T152722Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-586--task-OOMPAH-594
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:28:34.786015+00:00'
  - run_id: OOMPAH-594__20260730T152851Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: security
    source_branch: epic-OOMPAH-586--task-OOMPAH-594
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:29:23.210006+00:00'
---
## Summary

Implementation scope

Prevent the running service from retaining stale HTTP Basic verifier state after the configured htpasswd file is atomically replaced or updated. Detect safe file identity/content changes, load and validate a complete replacement atomically, preserve the last known-good credentials on parse/read failure, and expose a redacted reload status. Ensure Makefile lifecycle clients and task/admin CLIs use the current .env client inputs; do not pass Basic credentials to workers. Relevant files include oompah/http_auth.py, bootstrap/server auth middleware, client lifecycle helpers, Makefile/scripts/oompah_http.py, and .env.example/operator docs if behavior changes.

Tests

Cover valid rotation, invalid/partial replacement, symlink/path protections, concurrent requests, username removal/addition, unchanged files, restart parity, and secret redaction. Run focused auth/server tests and make test.

Acceptance criteria

Supported credential rotation does not require an unauthenticated force restart; operator status, restart, task, and admin commands authenticate after rotation; malformed updates never disable or weaken auth.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 15:19
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:19
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 15:22
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 58, Tool calls: 25
- Tokens: 10 in / 972 out [982 total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 40s
- Log: OOMPAH-594__20260730T152001Z.jsonl
---
author: oompah
created: 2026-07-30 15:27
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:27
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 15:28
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 48, Tool calls: 26
- Tokens: 146 in / 4.4K out [4.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 21s
- Log: OOMPAH-594__20260730T152722Z.jsonl
---
author: oompah
created: 2026-07-30 15:28
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 15:28
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-30 15:29
---
Agent completed successfully in 40s (46568 tokens)
---
author: oompah
created: 2026-07-30 15:29
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 1
- Tokens: 46.1K in / 454 out [46.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 40s
- Log: OOMPAH-594__20260730T152851Z.jsonl
---
author: oompah
created: 2026-07-30 15:29
---
Agent completed without closing this issue (40s (46568 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
