---
id: OOMPAH-298
type: task
status: Open
priority: 1
title: Inject task-relevant repository maps into agent focus startup prompts
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-296
- OOMPAH-297
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T15:14:08.542161Z'
updated_at: '2026-07-21T23:01:33.451152Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 147608ab-c362-470b-b6ac-11da9096b875
oompah.task_costs:
  total_input_tokens: 348934
  total_output_tokens: 2747
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 348934
      output_tokens: 2747
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 182988
    output_tokens: 1405
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:00:32.918132+00:00'
  - profile: standard
    model: unknown
    input_tokens: 165946
    output_tokens: 1342
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:01:29.940331+00:00'
---
## Summary

Integrate repository maps into the agent prompt assembly path. Resolve the agent checkout commit, load only a fresh matching artifact, derive seeds from the task title, description, linked files, PR/commit data, and focus handoff, then render a token-budgeted map with OOMPAH-296. Insert it into every focus startup prompt in a clearly labeled untrusted repository-context block. Preserve the existing prompt when no fresh map is available. Do not expose data from another project, branch, or commit.\n\nTests:\n- Prompt tests verify a fresh matching map is included for each focus type.\n- Verify stale SHA, wrong project, missing artifact, and rendering failure omit the map and retain normal startup.\n- Verify the configured token ceiling is respected and task-specific seeds affect selection.\n- Verify the prompt labels repository text as data, not instructions, and cannot override system/task instructions.\n\nAcceptance criteria:\n- Newly started agents receive a bounded, relevant map without needing extra model round trips.\n- No startup is blocked by map generation or retrieval failure.\n- Prompt provenance and SHA are available in agent diagnostics.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 22:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 23:00
---
Agent completed successfully in 40s (184393 tokens)
---
author: oompah
created: 2026-07-21 23:00
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 4
- Tokens: 183.0K in / 1.4K out [184.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 40s
- Log: OOMPAH-298__20260721T225954Z.jsonl
---
author: oompah
created: 2026-07-21 23:00
---
Agent completed without closing this issue (40s (184393 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 23:00
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 23:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 23:01
---
Understanding: I screened OOMPAH-298 for overlap with the repository-map work. This task is the downstream prompt-assembly consumer: it must safely select a fresh project-and-checkout-SHA map, derive task/focus seeds, and inject a bounded untrusted context block without affecting startup on failure. I will complete duplicate screening before implementation handoff.
---
author: oompah
created: 2026-07-21 23:01
---
Duplicate screening complete: no duplicate confirmed. Closest reviewed tasks: OOMPAH-296 (Merged) implements task-seeded, token-bounded ranking/rendering only and explicitly does not alter prompts; OOMPAH-297 (Done) generates/persists fresh SHA-keyed artifacts on state branches only. OOMPAH-298 is the distinct downstream agent prompt integration layer. Repository search found only the artifact design (plans/repo-map-artifact.md); no existing task covers startup-prompt injection, provenance diagnostics, or fail-open prompt behavior.
---
author: oompah
created: 2026-07-21 23:01
---
Focus handoff: duplicate_detector\n\n1. Outcome: No duplicate confirmed; OOMPAH-298 is net-new prompt integration work.\n2. Evidence: Read full OOMPAH-296 and OOMPAH-297 task descriptions/comments. OOMPAH-296 provides oompah/repo_map_ranker.py with rank_symbols/render_repo_map; OOMPAH-297 provides oompah/repo_map_generator.py and fresh, SHA-scoped state-branch artifacts. plans/repo-map-artifact.md defines artifact freshness and isolation.\n3. Remaining work/risks: locate focus prompt assembly and agent diagnostics; resolve the actual checkout SHA; read only artifacts matching project plus SHA; derive seeds from task title/description/files/PR-commit data/handoff; call bounded renderer; wrap result as untrusted repository data; swallow retrieval/render failures; add tests for every focus and isolation/failure/budget/provenance cases. Do not trigger generation during startup.\n4. Recommended next focus: feature.
---
author: oompah
created: 2026-07-21 23:01
---
Agent completed successfully in 40s (167288 tokens)
---
author: oompah
created: 2026-07-21 23:01
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 165.9K in / 1.3K out [167.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 40s
- Log: OOMPAH-298__20260721T230051Z.jsonl
---
author: oompah
created: 2026-07-21 23:01
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
<!-- COMMENTS:END -->
