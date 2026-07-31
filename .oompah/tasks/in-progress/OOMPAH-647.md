---
id: OOMPAH-647
type: task
status: In Progress
priority: null
title: Make merge-conflict rebase continuation noninteractive and deadlock-safe
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T07:09:27.752943Z'
updated_at: '2026-07-31T07:15:24.067901Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 68fcb9c97245c8ffaa75c53536a9ffa3c84fea1bb8ec55c467315ac0a4a26565
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T07:10:54.566738+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Only active native task is OOMPAH-281, covering a self-hosted CI runner.
    Closest matches OOMPAH-214 (Archived, conflict-agent dispatch) and OOMPAH-235
    (Archived, tracker rebase recovery) are terminal and do not cover noninteractive
    rebase continuation/editor deadlock prevention.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: f04374c6-0574-41a8-8715-8a7b627a01d5
oompah.task_costs:
  total_input_tokens: 269782
  total_output_tokens: 1487
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 269782
      output_tokens: 1487
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 269782
    output_tokens: 1487
    cost_usd: 0.0
    recorded_at: '2026-07-31T07:10:54.563272+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-647__20260731T070958Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: duplicate_detector
    source_branch: OOMPAH-647
    source_sha: 50625abed5be36e106dbd281871a2e464c671303
    completed_at: '2026-07-31T07:10:54.580031+00:00'
---
## Summary

Live deadlock on 2026-07-31 while recovering OOMPAH-643/PR #610: the Merge Conflict Resolver correctly resolved and staged terminal_transition_coordinator.py, then ran 'git add ... && git rebase --continue'. Git spawned /usr/bin/vi on .git/worktrees/OOMPAH-643/COMMIT_EDITMSG and the ACP tool call blocked from 07:05:37 until the operator terminated only the editor PID at 07:08:40; the same agent then resumed and completed the rebase at 2b3a967c8. Implementation scope: ensure every server-generated merge/rebase continuation path is explicitly noninteractive (for example GIT_EDITOR=true/GIT_SEQUENCE_EDITOR=true or git -c core.editor=true as appropriate), preserves the original commit message and required attribution trailer, and cannot inherit an interactive editor from the host. Add bounded command monitoring so an unexpected editor/prompt is terminated and reported/retried without discarding staged conflict resolution. Cover resolver prompts, command wrappers/MCP policy, retry/recovery, and any automated rebase helpers. Required tests: real repository conflict with an unset editor; hostile EDITOR pointing to a blocking executable that must never be invoked; continuation success and preserved message/trailers; unexpected prompt timeout retains recoverable rebase state; repeated recovery is idempotent. Acceptance: OOMPAH-643-style rebase continuation completes unattended, no vi/editor child can deadlock an agent slot, focused conflict-resolver/process tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 07:09
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-31 07:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 07:10
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 6
- Tokens: 269.8K in / 1.5K out [271.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 5s
- Log: OOMPAH-647__20260731T070958Z.jsonl
---
author: oompah
created: 2026-07-31 07:11
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-31 07:11
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-07-31 07:15
---
**Understanding**: OOMPAH-643 deadlock: the merge-conflict resolver ran 'git rebase --continue' which caused git to spawn /usr/bin/vi on the COMMIT_EDITMSG, blocking the ACP tool call for ~3 minutes until the operator killed the editor PID.\n\n**Planned approach:**\n1. Create `oompah/git_noninteractive.py` with a `NONINTERACTIVE_GIT_ENV` dict (`GIT_EDITOR=true`, `GIT_SEQUENCE_EDITOR=true`, `GIT_TERMINAL_PROMPT=0`) and a `run_rebase_continue()` helper with bounded subprocess timeout/kill monitoring.\n2. Update `oompah/integration_executor.py` `_git()` to always pass `NONINTERACTIVE_GIT_ENV` so the server-side rebase operations can never spawn an editor.\n3. Update `oompah/cherry_pick_pr_creator.py` subprocess calls to also pass noninteractive env.\n4. Update `oompah/focus.py` merge_conflict focus must_do list to instruct agents to use `GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true` before `git rebase --continue`.\n5. Add `tests/test_git_noninteractive.py` with the five required test scenarios.\n\n**Key insight**: The fix has two layers — (a) server-side subprocess calls must set noninteractive env, (b) the agent prompt instructions must tell agents to use the same env when they run git commands.
---
<!-- COMMENTS:END -->
