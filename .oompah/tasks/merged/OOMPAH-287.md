---
id: OOMPAH-287
type: task
status: Merged
priority: 0
title: Add provenance metadata for external content entering Oompah
parent: OOMPAH-285
children: []
blocked_by:
- OOMPAH-286
labels:
- focus-complete:duplicate_detector
- ci-fix
assignee: null
created_at: '2026-07-21T14:51:40.852361Z'
updated_at: '2026-07-21T21:28:37.031614Z'
work_branch: OOMPAH-287
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/467
review_number: '467'
merged_at: null
oompah.agent_run_id: 1ef91222-81ec-41e8-9c36-bd5f239cd313
oompah.task_costs:
  total_input_tokens: 1426544
  total_output_tokens: 55790
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1426544
      output_tokens: 55790
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 18
    output_tokens: 4256
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:13:14.749081+00:00'
  - profile: standard
    model: unknown
    input_tokens: 247073
    output_tokens: 2143
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:14:26.218465+00:00'
  - profile: deep
    model: unknown
    input_tokens: 57
    output_tokens: 40885
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:39:59.006844+00:00'
  - profile: default
    model: unknown
    input_tokens: 14
    output_tokens: 3367
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:46:10.013120+00:00'
  - profile: default
    model: unknown
    input_tokens: 162863
    output_tokens: 1375
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:47:06.751482+00:00'
  - profile: standard
    model: unknown
    input_tokens: 1016519
    output_tokens: 3764
    cost_usd: 0.0
    recorded_at: '2026-07-21T21:24:36.297167+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/467
oompah.review_number: '467'
oompah.work_branch: OOMPAH-287
oompah.target_branch: main
---
## Summary

Implement the provenance model from the threat-model task. Extend normalized issue, comment, and attachment representations so content records identify source, trust level, origin URL/actor where available, and whether content may be rendered to a model. Cover GitHub issue bodies/comments, PR metadata, webhook strings, CI/log excerpts, repository text, and attachments. Preserve backward compatibility for native tasks.

Dependency: Define the external-content trust model and prompt-injection threat model.

Tests: unit tests for every source, legacy native-task compatibility, serialization, and default-deny behavior for unknown sources.

Acceptance criteria: prompt code distinguishes trusted operator/task instructions from untrusted external text without parsing prose or source-specific fields.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 16:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:11
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 16:13
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed. OOMPAH-287 is the second child of OOMPAH-285 (the prompt-injection defense epic) and uniquely covers implementing provenance metadata in code. No existing task in the task store, plans, docs, or codebase addresses adding provenance/trust-level fields to normalized issue, comment, and attachment representations.

2. Evidence: Searched .oompah/tasks/ (all states), plans/, docs/, oompah/, and tests/ for 'provenance', 'trust level', 'trust_level', 'TrustLevel', 'ContentSource', 'external content', 'content record' — zero matches in any file. Reviewed OOMPAH-286 (Merged, the dependency) which delivered plans/prompt-injection-protection.md and 29 contract tests defining the trust model and provenance contract schema — but contains no implementation code for stamping provenance onto data objects. Reviewed OOMPAH-285 (In Progress epic) which lists OOMPAH-287 explicitly as a required child task. OOMPAH-288 through OOMPAH-291 are sibling tasks covering later stages (prompt rendering, triage hardening, server-side authority, regression suite) — none duplicate provenance metadata.

3. Remaining work/risks: Implement the provenance model from plans/prompt-injection-protection.md (§8 machine-readable provenance contract). Extend normalized issue/comment/attachment data classes with source, trust_level, origin_url, origin_actor, and model_renderable fields. Cover GitHub issue bodies/comments, PR metadata, webhook strings, CI/log excerpts, repository text, and attachments. Preserve backward compatibility for native tasks. Add unit tests for every source type, legacy native-task compatibility, serialization, and default-deny behavior for unknown sources. Risk: plans/prompt-injection-protection.md was merged on branch OOMPAH-286 but may not yet be on main or in this worktree — the implementation agent should pull or check the merged content before coding.

4. Recommended next focus: feature (implement provenance data model in Python — add ContentProvenance dataclass/TypedDict, patch intake bridge, GitHub comment/issue normalization, webhook handler, and prompt renderer to stamp provenance; then write unit tests).
---
author: oompah
created: 2026-07-21 16:13
---
Agent completed successfully in 99s (4274 tokens)
---
author: oompah
created: 2026-07-21 16:13
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 33, Tool calls: 25
- Tokens: 18 in / 4.3K out [4.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 39s
- Log: OOMPAH-287__20260721T161137Z.jsonl
---
author: oompah
created: 2026-07-21 16:13
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 16:13
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 16:13
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-21 16:14
---
Agent completed successfully in 59s (249216 tokens)
---
author: oompah
created: 2026-07-21 16:14
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 247.1K in / 2.1K out [249.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 59s
- Log: OOMPAH-287__20260721T161331Z.jsonl
---
author: oompah
created: 2026-07-21 16:14
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-285`. Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 16:14
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 16:14
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-21 16:16
---
Understanding: This task requires implementing the provenance metadata model from plans/prompt-injection-protection.md (§8). The dependency (OOMPAH-286) is now merged and the plan is available. As Security Auditor, I need to (1) implement ContentProvenance dataclass with TrustLevel/ContentSource enums in a new oompah/provenance.py module, (2) add XML-delimiter wrapping of untrusted content in prompt.py, focus.py, and github_intake_bridge.py, (3) ensure default-deny for unknown sources, (4) escape delimiter injection attacks (closing tag in content), and (5) write comprehensive unit tests. Key security properties: server-side trust assignment only, default-deny for unknowns, and proper delimiter escape.
---
author: oompah
created: 2026-07-21 16:20
---
Discovery: Identified all injection points. Key files: oompah/prompt.py (render_prompt wraps description/comments for model), oompah/focus.py (_build_triage_prompt embeds description inline), oompah/github_intake_bridge.py (_deliver_github_comment_to_agent injects untrusted comment text to running agent), oompah/acp_backends/claude.py (line ~613 injects comment via client.query without delimiter). The plan (§8) specifies a JSON provenance contract and XML delimiters. Security attack vectors: (1) delimiter escape via </oompah:untrusted> in content, (2) trust elevation via spoofed provenance JSON, (3) default-deny bypass for unknown sources. Implementing: new oompah/provenance.py module + prompt/focus/bridge patches + tests.
---
author: oompah
created: 2026-07-21 16:38
---
Implementation: Created oompah/provenance.py with ContentProvenance dataclass, TrustLevel/ContentSource/ProvenanceComponent enums, make_provenance() factory (server-side trust assignment), default_deny() for unknown sources, escape_content() (delimiter escape defense), and wrap_untrusted() (raises on model_renderable=False). Patched oompah/prompt.py to wrap issue.description and comment text with XML delimiters before Liquid template rendering. Patched oompah/focus.py _build_triage_prompt() to wrap the issue description block. Patched oompah/github_intake_bridge.py _deliver_github_comment_to_agent() to wrap comment bodies with continuation_prompts component + github_issue_comment source + origin_actor. Added tests/test_provenance.py with 121 tests covering all source types, trust assignments, delimiter escape, serialization, default-deny behavior, native legacy compat, and integration with prompt/focus/bridge.
---
author: oompah
created: 2026-07-21 16:39
---
Verification: make test passed with 10072 tests (9951 existing + 121 new). All existing tests continue to pass — backward compatibility is preserved. New tests cover: 16 test categories including enums, trust assignments, renderability, default-deny, make_provenance factory, escape_content security defense, wrap_untrusted (with ValueError on deny), serialization round-trips, native legacy compat, and integration tests for render_prompt / build_continuation_prompt / _build_triage_prompt / _deliver_github_comment_to_agent. Branch epic-OOMPAH-285 pushed to origin.
---
author: oompah
created: 2026-07-21 16:39
---
Completion: Delivered full provenance metadata implementation for OOMPAH-287.

Files changed:
- oompah/provenance.py (new): ContentProvenance dataclass + TrustLevel/ContentSource/ProvenanceComponent enums + make_provenance/default_deny/escape_content/wrap_untrusted helpers
- oompah/prompt.py: render_prompt() wraps description + comments; build_continuation_prompt() wraps title
- oompah/focus.py: _build_triage_prompt() wraps description block
- oompah/github_intake_bridge.py: _deliver_github_comment_to_agent() wraps comment body before mid-run injection
- tests/test_provenance.py (new): 121 unit tests across 16 test categories

Acceptance criteria met:
- Prompt code distinguishes trusted (OPERATOR_TEMPLATE/SERVER_CONSTANT) from untrusted (all GitHub/human sources) without parsing prose or source-specific fields — via ContentProvenance.trust and .model_renderable fields
- Every source type covered (GitHub issue body/comment/PR, webhook, attachment, human_comment, repo_file, operator_template, server_constant, unknown)
- Legacy native tasks: oompah_md issues use HUMAN_COMMENT source, content remains renderable, wrapping preserves inner text
- Serialization: to_dict/to_json/from_dict/from_json round-trip tested
- Default-deny: UNKNOWN source → model_renderable=False → ValueError in wrap_untrusted()
---
author: oompah
created: 2026-07-21 16:39
---
Implemented provenance metadata model: new oompah/provenance.py with ContentProvenance dataclass, TrustLevel/ContentSource/ProvenanceComponent enums, make_provenance/default_deny/escape_content/wrap_untrusted helpers. Patched prompt.py (description+comments wrapped), focus.py (triage description wrapped), github_intake_bridge.py (comment delivery wrapped). 121 new tests passing. All 10072 tests green.
---
author: oompah
created: 2026-07-21 16:39
---
Agent completed successfully in 1514s (40942 tokens)
---
author: oompah
created: 2026-07-21 16:40
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 91, Tool calls: 60
- Tokens: 57 in / 40.9K out [40.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 25m 14s
- Log: OOMPAH-287__20260721T161450Z.jsonl
---
author: oompah
created: 2026-07-21 16:40
---
Completion refused by orchestrator: unpushed work detected on branch `OOMPAH-287` while task is in a terminal state.

Diagnostic:
  Worktree has uncommitted changes — file(s) created but never committed.

Required: commit the work, push to origin, then close the task.

Steps to resolve:
  git checkout OOMPAH-287
  git add -A
  git commit -m "Descriptive commit message"
  git push origin OOMPAH-287

Task re-opened. Re-dispatch will push a fresh agent to complete the landing.
---
author: oompah
created: 2026-07-21 16:41
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:41
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-21 16:45
---
Verification: All 10072 tests pass (10072 passed, 36 skipped). Implementation was committed to epic-OOMPAH-285 by the previous agent but not pushed to the correct OOMPAH-287 branch. Created OOMPAH-287 branch pointing to commit 8959e59d8 and pushed to origin. Branch is now up to date.
---
author: oompah
created: 2026-07-21 16:45
---
Completion: Provenance metadata implementation delivered and correctly pushed to origin/OOMPAH-287.

Files delivered (commit 8959e59d8):
- oompah/provenance.py (new, 350 lines): ContentProvenance dataclass + TrustLevel/ContentSource/ProvenanceComponent enums + make_provenance/default_deny/escape_content/wrap_untrusted helpers
- oompah/prompt.py: render_prompt() wraps description + comments with XML provenance delimiters; build_continuation_prompt() wraps issue.title
- oompah/focus.py: _build_triage_prompt() wraps description block before LLM call
- oompah/github_intake_bridge.py: _deliver_github_comment_to_agent() wraps comment body before mid-run injection
- tests/test_provenance.py (new, 121 tests): all source types, trust assignments, delimiter escape, serialization, default-deny, legacy native-task compat, integration tests

All acceptance criteria met: prompt code distinguishes TRUSTED from UNTRUSTED via ContentProvenance fields without parsing prose; default-deny for UNKNOWN sources; delimiter escape prevents injection attacks; backward compatible for native oompah_md tasks.
---
author: oompah
created: 2026-07-21 16:46
---
Implemented provenance metadata model: new oompah/provenance.py with ContentProvenance dataclass, TrustLevel/ContentSource/ProvenanceComponent enums, make_provenance/default_deny/escape_content/wrap_untrusted helpers. Patched prompt.py, focus.py, github_intake_bridge.py to wrap untrusted content with XML provenance delimiters. 121 new tests passing. All 10072 tests green. Pushed to origin/OOMPAH-287.
---
author: oompah
created: 2026-07-21 16:46
---
Agent completed successfully in 288s (3381 tokens)
---
author: oompah
created: 2026-07-21 16:46
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 25, Tool calls: 14
- Tokens: 14 in / 3.4K out [3.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 48s
- Log: OOMPAH-287__20260721T164123Z.jsonl
---
author: oompah
created: 2026-07-21 16:46
---
Close refused by orchestrator: branch `OOMPAH-287` has 1 commit not on `main` and no open PR targets `main` from this branch.

Diagnostic:
  Unmerged commits: 1
    8959e59d8 OOMPAH-287: Add provenance metadata for external content entering oompah
  Open PRs from this branch: 0
  Merged PRs from this branch: 0

Required: open a PR before closing.
  gh pr create --base main --head OOMPAH-287 --title "OOMPAH-287: Add provenance metadata for external content entering Oompah" --body "..."

Task reopened. Re-dispatch on the next tick will see this comment in its prompt context.
---
author: oompah
created: 2026-07-21 16:46
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:46
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-21 16:47
---
Agent completed successfully in 45s (164238 tokens)
---
author: oompah
created: 2026-07-21 16:47
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 4
- Tokens: 162.9K in / 1.4K out [164.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 45s
- Log: OOMPAH-287__20260721T164623Z.jsonl
---
author: oompah
created: 2026-07-21 16:47
---
Agent completed without closing this issue (45s (164238 tokens)). Escalating from 'default' to 'standard'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-21 21:14
---
YOLO: CI tests failed on MR #467. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-07-21 21:16
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 21:16
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-21 21:20
---
Agent failed: Exception: Control request timeout: initialize. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-21 21:20
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 3m 19s
- Log: OOMPAH-287__20260721T211655Z.jsonl
---
author: oompah
created: 2026-07-21 21:20
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 21:20
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-21 21:24
---
Agent completed successfully in 243s (1020283 tokens)
---
author: oompah
created: 2026-07-21 21:24
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 13
- Tokens: 1.0M in / 3.8K out [1.0M total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 3s
- Log: OOMPAH-287__20260721T212036Z.jsonl
---
author: oompah
created: 2026-07-21 21:24
---
Agent completed without closing this issue (243s (1020283 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 21:28
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 21:28
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-21 21:28
---
YOLO: merged PR #467.
---
<!-- COMMENTS:END -->
