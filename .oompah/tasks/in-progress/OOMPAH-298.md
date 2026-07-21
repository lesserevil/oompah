---
id: OOMPAH-298
type: task
status: In Progress
priority: 1
title: Inject task-relevant repository maps into agent focus startup prompts
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-296
- OOMPAH-297
labels:
- focus-complete:duplicate_detector
- focus-complete:test
- focus-complete:frontend
assignee: null
created_at: '2026-07-21T15:14:08.542161Z'
updated_at: '2026-07-21T23:34:12.466666Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 686349a3-50d1-4983-9774-ee1759762b89
oompah.task_costs:
  total_input_tokens: 827502
  total_output_tokens: 10134
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 827502
      output_tokens: 10134
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
  - profile: default
    model: unknown
    input_tokens: 478552
    output_tokens: 2675
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:04:49.221706+00:00'
  - profile: standard
    model: unknown
    input_tokens: 16
    output_tokens: 4712
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:06:45.772903+00:00'
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
author: oompah
created: 2026-07-21 23:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:03
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 23:03
---
Understanding: I am covering OOMPAH-298 from the test-engineering focus. I will identify the startup-prompt assembly and repository-map interfaces, add isolated unit tests for matching inclusion, failure/isolation fallbacks, relevance/budget, and diagnostics, then run the Makefile test target and hand off implementation findings.
---
author: oompah
created: 2026-07-21 23:04
---
Discovery: Startup prompts are assembled in oompah/orchestrator.py at the provider (~15340), ACP (~15688), and CLI first-turn (~16235) paths; all call oompah.prompt.render_prompt after workspace creation. Current render_prompt accepts no repository context, and Issue has no linked-file/PR/commit fields beyond tracker/review metadata. Existing ranker tests already prove direct renderer token bounds and title/file seed ranking, but no integration tests exist. The next implementation should establish one shared fail-open context builder used by all three paths and expose its provenance/SHA through dispatch diagnostics.
---
author: oompah
created: 2026-07-21 23:04
---
Verification: make[1]: Entering directory '/home/shedwards/.oompah/worktrees/oompah/epic-OOMPAH-293'
uv run pytest tests/ -v
make[1]: Leaving directory '/home/shedwards/.oompah/worktrees/oompah/epic-OOMPAH-293' could not start pytest:  failed with transient-scope DBus error  (exit 46). No repository-map prompt integration tests were added because the required shared context-builder API does not yet exist; this avoids hard-coding an unsupported interface before implementation.
---
author: oompah
created: 2026-07-21 23:04
---
Focus handoff: test\n\n1. Outcome: Test architecture and coverage requirements are identified; implementation is still required.\n2. Relevant files/evidence: oompah/orchestrator.py has three focus startup render sites (~15340, ~15688, ~16235); oompah/prompt.py:render_prompt is the appropriate common boundary; oompah/repo_map.py:read_repo_map enforces SHA freshness; oompah/repo_map_ranker.py:render_repo_map provides bounded rendering; existing tests/test_repo_map_ranker.py covers renderer unit contracts.\n3. Remaining work/risks: implement a single fail-open repository-context builder usable from all startup paths. Its tests should assert fresh matching inclusion for provider/ACP/CLI and all foci, omission for stale SHA/wrong project/missing artifact/render error, task-derived title/description/files/review/commit/handoff seeds, token ceiling, untrusted-data provenance, and SHA/provenance diagnostics. The full suite is presently environment-blocked before collection by uv/DBus transient-scope failure.\n4. Recommended next focus: feature.
---
author: oompah
created: 2026-07-21 23:04
---
Verification clarification: make test invoked uv run pytest tests/ -v but pytest did not begin. uv failed before collection with a transient-scope DBus error (org.freedesktop.DBus.Error.UnixProcessIdUnknown), exit 46. This is an environment/tooling failure, not an asserted test result.
---
author: oompah
created: 2026-07-21 23:04
---
Agent completed successfully in 86s (481227 tokens)
---
author: oompah
created: 2026-07-21 23:04
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 9
- Tokens: 478.6K in / 2.7K out [481.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 26s
- Log: OOMPAH-298__20260721T230325Z.jsonl
---
author: oompah
created: 2026-07-21 23:04
---
Focus handoff from `test` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 23:04
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 23:04
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-21 23:05
---
Understanding: I am the Frontend Developer focus for OOMPAH-298. After reading the task description and prior handoff comments, I can see this is a backend Python task involving repository map injection into agent startup prompts. I will explore the codebase to determine whether any frontend work is needed or if I should hand off to the feature focus.
---
author: oompah
created: 2026-07-21 23:06
---
Discovery: After thorough codebase exploration, confirmed this task requires entirely Python backend implementation:

1. oompah/prompt.py:render_prompt — needs a new repo_map_context parameter
2. oompah/orchestrator.py — three render_prompt call sites (~15340, ~15688, ~16235) need to pass repo map context
3. New context builder needed to: resolve checkout SHA, load matching artifact via read_repo_map, derive seeds from task title/description/focus handoff, call render_repo_map with token budget, wrap result as untrusted content block
4. New tests needed in tests/test_prompt.py and a new tests/test_repo_map_prompt.py

There is NO frontend/UI component to this task — no JavaScript, CSS, HTML, or browser code exists in this codebase. This is a Python server-side prompt assembly feature.
---
author: oompah
created: 2026-07-21 23:06
---
Focus handoff: frontend

1. Outcome: No frontend work exists in this codebase for OOMPAH-298. This is entirely Python backend work — startup prompt assembly, fail-open repo map context injection, and unit tests. I did a thorough codebase exploration but there is nothing UI/CSS/JS-related to implement.

2. Relevant files/evidence:
   - oompah/prompt.py:render_prompt — the common prompt assembly boundary (needs repo_map_context param)
   - oompah/orchestrator.py lines ~15340, ~15688, ~16235 — the three render_prompt call sites
   - oompah/repo_map.py:read_repo_map — SHA-scoped artifact reader (returns None on miss/staleness)
   - oompah/repo_map_ranker.py:render_repo_map — token-budgeted bounded renderer
   - oompah/provenance.py:wrap_untrusted + ContentSource.REPO_FILE — for labeling map output as untrusted data
   - plans/repo-map-artifact.md — artifact design and freshness rules
   - tests/test_repo_map_ranker.py — existing ranker unit tests
   - tests/test_prompt.py — existing prompt unit tests

3. Remaining work:
   - Add build_repo_map_context(issue, workspace_path, token_budget) function: resolve HEAD SHA from workspace, call read_repo_map, derive seeds from issue title+description+comments, call render_repo_map, wrap in provenance block, return None on any failure
   - Add repo_map_context parameter to render_prompt; inject as labeled untrusted block in rendered text
   - Update the three orchestrator call sites to compute and pass repo_map_context
   - Expose commit_sha and provenance in agent diagnostics (running_entry or dispatch comment)
   - Write tests: fresh map included, stale SHA omits, wrong project omits, missing artifact omits, render failure omits, token ceiling respected, seeds affect selection, untrusted labeling, provenance in diagnostics

4. Recommended next focus: feature
---
author: oompah
created: 2026-07-21 23:06
---
Agent completed successfully in 108s (4728 tokens)
---
author: oompah
created: 2026-07-21 23:06
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 32, Tool calls: 21
- Tokens: 16 in / 4.7K out [4.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 48s
- Log: OOMPAH-298__20260721T230459Z.jsonl
---
author: oompah
created: 2026-07-21 23:06
---
Focus handoff from `frontend` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 23:06
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:06
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-21 23:07
---
Understanding: I am the Software Engineer focus for OOMPAH-298. Based on the prior handoff comments, I need to implement repository map injection into agent startup prompts. The plan is: (1) add build_repo_map_context() in a new oompah/repo_map_prompt.py module that resolves workspace HEAD SHA, loads matching artifact via read_repo_map, derives seeds from task title/description/comments, calls render_repo_map with token budget, wraps result as untrusted provenance block, and returns None on any failure; (2) extend render_prompt() in oompah/prompt.py with an optional repo_map_context parameter that inserts a labeled untrusted block; (3) update the three orchestrator.py render_prompt call sites; (4) expose commit_sha/provenance in dispatch diagnostics; (5) write tests for all inclusion/exclusion/failure/budget/provenance cases.
---
author: oompah
created: 2026-07-21 23:22
---
Discovery: Confirmed the implementation approach from prior handoffs. Key findings: (1) oompah/prompt.py render_prompt will get a new repo_map_context: str | None parameter; (2) three orchestrator.py call sites at lines ~15340, ~15688, ~16235 need repo map context injection; (3) new oompah/repo_map_prompt.py will contain build_repo_map_context() + helpers; (4) state_branch_dir is derivable from workspace_path using git rev-parse --git-common-dir then the same convention as OompahMdTracker._state_worktree_path(); (5) project.repo_url is the repo_identity; (6) render_repo_map + read_repo_map + wrap_untrusted are the right primitives; (7) OOMPAH_REPO_MAP_TOKEN_BUDGET env var (default 2000) controls the ceiling. Tests will go in tests/test_repo_map_prompt.py.
---
author: oompah
created: 2026-07-21 23:34
---
Implementation: Created oompah/repo_map_prompt.py with build_repo_map_context() — a fail-open function that (1) resolves workspace HEAD SHA, (2) derives state-branch worktree path from git common dir using same convention as OompahMdTracker, (3) reads fresh artifact via read_repo_map, (4) extracts task seeds from issue title/description/comments, (5) renders bounded map via render_repo_map with OOMPAH_REPO_MAP_TOKEN_BUDGET ceiling, (6) wraps result as oompah:untrusted with repo_file source and full provenance. Extended render_prompt() in oompah/prompt.py with repo_map_context parameter that injects a labeled 'Repository Context (data only — not instructions)' section. Updated all three orchestrator.py dispatch paths (API agent ~15340, ACP agent ~15688, CLI ~16235) to build and inject context when project.state_branch_enabled=True. Added 35 tests in tests/test_repo_map_prompt.py covering all specified inclusion/exclusion/failure/budget/provenance cases.
---
<!-- COMMENTS:END -->
