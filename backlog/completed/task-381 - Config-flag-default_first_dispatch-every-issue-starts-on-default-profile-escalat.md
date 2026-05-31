---
id: TASK-381
title: 'Config flag default_first_dispatch: every issue starts on default profile,
  escalates to matched profile on first failure'
status: Done
assignee: []
created_date: 2026-05-05 19:50
updated_date: 2026-05-05 20:17
labels:
- feature
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: feature
beads:
  id: oompah-zlz_2-17u
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-zlz_2-17u
  target_branch: null
  url: null
  created_at: '2026-05-05T19:50:51Z'
  updated_at: '2026-05-05T20:17:46Z'
  closed_at: '2026-05-05T20:17:46Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Today the initial dispatch path (orchestrator.py:_match_agent_profile, _resolve_provider, _resolve_model) chooses the BEST agent profile + model for an issue based on issue_type / keywords / priority. A `bug` issue immediately routes to the `deep` profile and runs on Opus. A `task` runs on Sonnet. Only on RETRY do we walk back through the escalation hierarchy.

That's correct when the goal is "get this done well first try", but it's expensive when many issues would have succeeded just fine on the cheap default. With the new windowed budget ($50/hour), starting straight on Opus burns the cap fast even if 80% of the work didn't need it.

Add a config flag that inverts the logic for the FIRST transition to in_progress: every issue starts on the default profile / default model regardless of issue_type / keywords / priority, and ONLY escalates to its `_match_agent_profile`-chosen profile after a failed attempt (stall, max_turns, completed-without-closing). Subsequent retries continue to escalate up the hierarchy as today.

Naming: `OOMPAH_DEFAULT_FIRST_DISPATCH` env var + `agent.default_first_dispatch: true|false` in WORKFLOW.md. Default false (current behavior preserved).

Effective semantics with the flag on:
- Issue dispatched for the first time → profile = `default` (or whatever profile in WORKFLOW.md has the catch-all "no constraints" shape), model = provider.default_model.
- Agent stalls / hits max_turns / completes-without-closing → on retry, the escalation walk starts from the profile `_match_agent_profile` would have originally chosen, NOT from `default`. So a bug that needed Opus and stalled on MiniMax skips up to deep on the first retry rather than walking quick → standard → deep.
- `needs:<focus>` label still wins over the flag — user intent always overrides.

This is a quality-vs-cost knob. Combined with the per-task cost telemetry (oompah-zlz_2-qh8) we'll have data to tune whether `default_first_dispatch=true` is the right default; right now leave it opt-in.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df9b3-232c-746c-8077-d6342304a681
author: oompah
created: 2026-05-05T19:52:40Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9b3-53dc-77a1-95cc-9aad8ccf1487
author: oompah
created: 2026-05-05T19:52:52Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9b3-fa87-7683-976a-ed2137742ed4
author: oompah
created: 2026-05-05T19:53:35Z

Understanding: I've read orchestrator.py, config.py, models.py, and tests/test_config.py. Here's my implementation plan:

1. **config.py**: Add  to , parsed from  in WORKFLOW.md YAML, with  env var override.

2. **orchestrator.py **: When  is True AND  (first dispatch) AND no  is set AND no  label is present → use the default catch-all profile (one with no issue_type/keyword/priority constraints) instead of . Store the 'naturally matched' profile name in the runtime state so retries can escalate from the right starting point.

3. ** / retry logic**: When  is True and this is the first retry (was dispatched on default but failed), set  to 's result for the issue (what it *would* have gotten originally). Subsequent retries continue normal escalation from there.

4. ****: Include  in the state response.

5. **Tests**: Add tests covering flag-off (current behavior), flag-on first dispatch, flag-on retry after failure, needs:test label bypass, escalation continuation.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c3-3e50-7c11-bcaf-807d0e9ac9b2
author: oompah
created: 2026-05-05T20:10:16Z

Discovery: The key code locations are:
- oompah/config.py: ServiceConfig.from_workflow() builds config from WORKFLOW.md
- oompah/orchestrator.py: _dispatch() selects profiles, _on_worker_exit() schedules retries
- oompah/models.py: RunningEntry tracks running agent state

Implementation plan confirmed:
1. Add default_first_dispatch: bool to ServiceConfig + OOMPAH_DEFAULT_FIRST_DISPATCH env var
2. Add natural_profile_name field to RunningEntry (stores what _match_agent_profile() would pick)
3. Add helpers: _is_first_dispatch(), _has_explicit_handoff_label(), _get_default_catch_all_profile()
4. Update _dispatch() to use default profile on first dispatch when flag is on
5. Add _next_profile_for_retry() that jumps to natural profile on first retry
6. Update _on_worker_exit() retry paths to use _next_profile_for_retry()
7. Expose flag in get_snapshot() under config.default_first_dispatch
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c5-e2e2-749f-8ffe-4fe47a1d1d13
author: oompah
created: 2026-05-05T20:13:09Z

Implementation complete. Changes made:

**oompah/config.py**:
- Added default_first_dispatch: bool = False to ServiceConfig
- Added _env_bool() helper for boolean env var parsing
- Added OOMPAH_DEFAULT_FIRST_DISPATCH env var + agent.default_first_dispatch YAML support in from_workflow()

**oompah/models.py**:
- Added natural_profile_name: str | None = None to RunningEntry (stores the naturally-matched profile when dispatched on default)

**oompah/orchestrator.py**:
- Added _is_first_dispatch() helper
- Added _has_explicit_handoff_label() helper (needs:* bypass)
- Added _get_default_catch_all_profile() helper
- Updated _dispatch() to use catch-all default profile on first dispatch when flag=on (epics bypassed)
- Added _next_profile_for_retry() that jumps to natural_profile_name on first retry
- Updated _on_worker_exit() max_turns/stalled and completed_without_closing paths to use _next_profile_for_retry()
- Added config.default_first_dispatch to get_snapshot()

**.env.example**: Added OOMPAH_DEFAULT_FIRST_DISPATCH documentation

**tests/test_default_first_dispatch.py**: 49 new tests covering all acceptance criteria
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c9-d556-7c38-91e3-cabb24950f2f
author: oompah
created: 2026-05-05T20:17:27Z

Verification: All 49 new tests pass (plus 161 existing tests). Full test run: 210 passed, 0 failures in my changed files. 33 pre-existing failures in test_webhooks.py (require pytest-asyncio) are unrelated to this change.

Tests cover all acceptance criteria:
- Flag defaults to False (current behavior preserved)
- OOMPAH_DEFAULT_FIRST_DISPATCH env var + agent.default_first_dispatch YAML
- Bug issue dispatches on default profile first (not deep)
- natural_profile_name stored for correct first-retry escalation
- First retry after failure jumps to naturally-matched profile (deep for bug)
- Subsequent retries continue up _PROFILE_HIERARCHY normally
- needs:* labels bypass the flag
- Epics keep their existing routing (excluded from default_first_dispatch)
- get_snapshot() exposes config.default_first_dispatch in state API
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9ca-0405-7138-8aab-cdbf78c86cbc
author: oompah
created: 2026-05-05T20:17:39Z

Completion: Delivered the default_first_dispatch feature as specified.

Summary of all changes:
1. config.py: New bool field ServiceConfig.default_first_dispatch (default=False), _env_bool() helper, OOMPAH_DEFAULT_FIRST_DISPATCH env var + agent.default_first_dispatch YAML in from_workflow()
2. models.py: RunningEntry.natural_profile_name field to store originally-matched profile during default-first runs
3. orchestrator.py: Three new helper methods (_is_first_dispatch, _has_explicit_handoff_label, _get_default_catch_all_profile), updated _dispatch() with flag logic, new _next_profile_for_retry() implementing the jump-to-natural semantic, updated retry paths in _on_worker_exit(), added config.default_first_dispatch to get_snapshot()
4. .env.example: Documented OOMPAH_DEFAULT_FIRST_DISPATCH
5. tests/test_default_first_dispatch.py: 49 tests across 8 test classes

The flag is opt-in (default=false). Enable with OOMPAH_DEFAULT_FIRST_DISPATCH=1 or agent.default_first_dispatch: true in WORKFLOW.md.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9ca-2bcc-77b0-8acd-fd29ec86661f
author: oompah
created: 2026-05-05T20:17:50Z

Agent completed successfully in 1509s (8281455 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
