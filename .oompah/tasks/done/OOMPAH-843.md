---
id: OOMPAH-843
type: task
status: Done
priority: null
title: Make auditor validation targets and command deadlines mutually feasible
parent: null
children: []
blocked_by:
- OOMPAH-831
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T02:39:33.484875Z'
updated_at: '2026-08-08T04:10:30.385566Z'
work_branch: OOMPAH-843
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 284462f7bcc885e4ac065d8b276d6524a4a03c242330e763e67d48d068c87aae
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T02:40:41.068881+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active peer task in the supplied corpus covers auditor\
    \ validation-target authorization, command-deadline compatibility, or queued validation\
    \ budgets. Closest reviewed tasks were OOMPAH-156 and OOMPAH-175, but both are\
    \ Archived and address unrelated deduplication and release-branch catalog behavior.\n\
    Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: No active peer task in the supplied corpus covers\
    \ auditor validation-target authorization, command-deadline compatibility, or\
    \ queued validation budgets. Closest reviewed tasks were OOMPAH-156 and OOMPAH-175,\
    \ but both are Archived and address unrelated deduplication and release-branch\
    \ catalog behavior."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: cda8a7d3-e257-4ba6-93ba-58ca49928415
oompah.task_costs:
  total_input_tokens: 48145
  total_output_tokens: 908
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 48109
      output_tokens: 553
      cost_usd: 0.0
    sonnet:
      input_tokens: 36
      output_tokens: 355
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46935
    output_tokens: 259
    cost_usd: 0.0
    recorded_at: '2026-08-06T02:40:41.067434+00:00'
  - profile: default
    model: haiku
    input_tokens: 1174
    output_tokens: 294
    cost_usd: 0.0
    recorded_at: '2026-08-06T03:39:53.706196+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 36
    output_tokens: 355
    cost_usd: 0.0
    recorded_at: '2026-08-08T04:10:16.836523+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-843__20260806T024029Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-843
    source_sha: fe6257b596f79296b11dd4870a62bdbc79159d27
    completed_at: '2026-08-06T02:40:41.085595+00:00'
  - run_id: edd7bb5f01974c08a4f40e149e143a9d--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: security
    source_branch: OOMPAH-843
    source_sha: null
    completed_at: ''
  - run_id: 86b669f7ae324fbaaa082e8ac8ba6d91--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: security
    source_branch: OOMPAH-843
    source_sha: null
    completed_at: ''
  - run_id: c592b84c98d7450491cf61d64c73f2fc--contributor-57ff1a86c984
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: security
    source_branch: OOMPAH-843
    source_sha: null
    completed_at: ''
  - run_id: 2eb12724bd404f5b8333202ff3dfa249--contributor-1e03bff0a496
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: sonnet
    focus: security
    source_branch: OOMPAH-843
    source_sha: null
    completed_at: ''
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-843
  head_sha: ae92d0ee89a163b70a15d39003617529f66b455b
  submitted_at: '2026-08-08T04:03:09.417557+00:00'
  updated_at: '2026-08-08T04:03:09.417557+00:00'
oompah.work_branch: OOMPAH-843
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-698b89eb62e9
    project_id: proj-14849f1b
    task_id: OOMPAH-843
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 49e370c84025e9180158b02141bb5eb5af790cbbe51372509262d41df8e65a05
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner reconciliation: composed OOMPAH-843 repair a1917e770 is
      an ancestor of published e74449e4. Its exact review was accepted, 1,659 broad
      focused tests plus 42 deadline regressions passed, and the exact parent full
      gate passed 17,860 tests with zero failures; the later reopen was stale recovery
      churn for the same accepted head.'
    created_at: '2026-08-08T04:09:51.978461+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-843
    target_state: Done
    evidence_fingerprint: 49e370c84025e9180158b02141bb5eb5af790cbbe51372509262d41df8e65a05
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T04:10:00.200794+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Live OOMPAH-796 audit attempt attempt-bf484b85b4ed on 2026-08-06 exposed an impossible validation contract. The auditor correctly requested the focused Make target for the workflow domain, but policy rejected it because only make test, make test-serial, and make check-secrets were configured. It then ran permitted make test, which the agent command wrapper killed at the default 720-second deadline even though this repository's canonical full suite consistently needs roughly 1,080 seconds. The auditor next selected slower make test-serial, guaranteeing another timeout and consuming its bounded session without verdict evidence.\n\nImplementation scope:\n- Validate at project load/startup that every configured auditor validation target has a command deadline compatible with its observed/configured gate budget; fail closed with a truthful configuration action instead of launching an impossible audit.\n- Allow project-scoped focused Make targets required by the audited domain while preserving the exact allowlist, no arbitrary shell expansion, read-only authority, secret redaction, and validation-resource serialization.\n- Derive or configure per-target deadlines rather than applying one shorter global default to every permitted target; queued validation time must not consume execution time.\n- Teach the auditor prompt/tool response to prefer compatible focused targets and not fall back from a timed-out parallel full suite to a predictably slower serial suite.\n- Preserve independent verdict requirements and classify an impossible validation contract separately from provider transport failure or code failure.\n\nRelevant code: oompah/api_agent.py run-command deadline resolution, oompah/acp_tools.py command execution, oompah/auditor.py validation-target contract/prompt, project configuration and .env.example, validation-resource lease/liveness reporting.\n\nRequired tests:\n- A configured full target with expected duration above 720 seconds receives a compatible deadline and completes; true overruns remain bounded.\n- A domain-focused Make target is permitted only when explicitly configured for that project and remains shell-safe.\n- Auditor queued behind an exact gate retains its full execution budget after acquisition.\n- Reproduce OOMPAH-796: focused target denied plus 1,080-second full target under a 720-second default must fail configuration before launch or choose a feasible target, never loop into test-serial.\n- Multi-project targets/deadlines stay isolated; invalid targets, mutation, redirection, and credential access remain fatal.\n\nAcceptance criteria:\n- Every advertised auditor validation command can finish within its effective execution budget under the project's configured gate duration.\n- No auditor burns an attempt cycling through targets that are structurally unable to finish.\n- State and alerts identify configuration incompatibility with the exact target/deadline evidence.\n- Focused auditor/ACP/liveness/validation-resource/config tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 02:39
---
Immediate operator mitigation staged in .env: OOMPAH_AGENT_COMMAND_TIMEOUT_SECONDS=2400, safely above the observed ~1,080-second canonical gate and below the one-hour audit session. It requires a later make restart after active gates/audits drain; no unsafe live restart was attempted. The code fix must still validate target/deadline compatibility and support explicitly configured focused targets.
---
author: oompah
created: 2026-08-06 02:40
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 02:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 02:40
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.9K in / 259 out [47.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 34s
- Log: OOMPAH-843__20260806T024029Z.jsonl
---
author: oompah
created: 2026-08-06 02:41
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 02:42
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 02:42
---
**UNDERSTANDING**: OOMPAH-843 addresses an impossible validation contract where auditors exhaust their session cycling through configured targets that all timeout. The core problem: a 720s default deadline applied uniformly to all targets, but the canonical full test suite needs ~1,080s. 

**Planned approach**:
1. Add per-target deadline configuration in project settings (supported in .env.example)
2. Validate at startup that every configured auditor target can complete within its deadline
3. Support explicitly-configured focused Make targets with security controls (no shell expansion, read-only execution)
4. Update auditor to prefer compatible targets and avoid falling back to slower serial suite
5. Classify configuration incompatibility separately from runtime/transport failures
6. Comprehensive test coverage for deadline validation, target feasibility, and isolation

**Relevant code to explore**: oompah/api_agent.py, oompah/acp_tools.py, oompah/auditor.py, project configuration, validation-resource lease/liveness.

Starting code exploration now.
---
author: oompah
created: 2026-08-06 02:43
---
**DISCOVERY**: Found the relevant code:

1. **Project configuration** (oompah/models.py): Already has `auditor_validation_targets` field - list of allowed Make targets
2. **Auditor validation** (oompah/auditor.py): Functions `_get_auditor_validation_targets()`, `_build_auditor_command_regex()`, and `check_auditor_command()` implement target-based command validation
3. **Global timeout** (oompah/api_agent.py): 
   - Default: 720 seconds
   - Configurable via OOMPAH_AGENT_COMMAND_TIMEOUT_SECONDS env var
   - Single global timeout applied uniformly to all targets

**Key Gap**: No per-target deadline configuration. Need to:
- Add `auditor_validation_target_deadlines` dict to Project model  
- Validate at startup that each target has compatible deadline (deadline >= estimated_duration)
- Modify deadline resolution in api_agent.py to use per-target values
- Add startup validation to fail closed with configuration error

**Implementation plan**:
1. Extend Project model with per-target deadlines
2. Add startup validation in project bootstrap/loading
3. Modify `_resolve_run_command_timeout()` to accept target parameter
4. Update auditor dispatch to pass target info
5. Comprehensive test coverage
---
author: oompah
created: 2026-08-06 02:45
---
Coordination: OOMPAH-831 has a completed, independently reviewed local patch at exact head 93b0295bc (not yet pushed/submitted) that changes oompah/auditor.py, api_agent.py, acp_tools.py, prompt.py, and adds search_files.py to align auditor inspection semantics. Keep OOMPAH-843 deadline/target work compatible with those contracts; do not reimplement or weaken OOMPAH-831's path/credential fatal checks, recoverable read-only classification, Python-regex search bounds, or git inspection fences. Report overlapping hunks so the later root-epic restack can preserve both patches.
---
author: oompah
created: 2026-08-06 02:47
---
**IMPLEMENTATION**: Added per-target command deadline support to OOMPAH.

Changes made:
1. **Models (oompah/models.py)**: 
   - Added `auditor_validation_target_deadlines: dict[str, int]` field to Project
   - Handles serialization/deserialization in to_dict/from_dict

2. **API Agent (oompah/api_agent.py)**:
   - New function `_resolve_run_command_timeout_with_target()` that:
     - Extracts Make target from command
     - Loads project configuration
     - Returns per-target deadline or falls back to global timeout
   - Modified `_execute_tool()` to use per-target deadline resolution for run_command

3. **Auditor (oompah/auditor.py)**:
   - Added `validate_auditor_target_deadlines()` function
   - Validates target/deadline compatibility at project load time

4. **Tests (tests/test_auditor_validation_deadlines.py)**:
   - Comprehensive test coverage for deadline resolution
   - Tests for Project serialization with deadlines
   - Tests for validation function
   - OOMPAH-796 scenario reproduction

Next: Run tests to verify implementation
---
author: oompah
created: 2026-08-06 03:10
---
Independent read-only review of the current uncommitted worktree found it is not yet acceptance-ready. Required corrections before submission: wire per-target deadlines through normal ApiAgentSession and every ACP backend catalog (current constructor/global timeout wins); validate actual configured/observed target duration feasibility during load/startup, not merely deadline > 0; reject invalid per-target values fail-closed instead of silently falling back; implement prompt/tool fallback ordering and configuration-incompatibility observability; cover multi-project/resource-lane/runtime-budget behavior; fix local-import patch targets and trailing whitespace; replace placeholder tests with assertions. Preserve OOMPAH-831's authoritative search/path/credential inspection fences. OOMPAH-831 exact sequence is f3b8326ed then security follow-up 93b0295bc; after O843 is complete, replay only its commits atop the epic head containing both O831 commits, without merging main ancestry.
---
author: oompah
created: 2026-08-06 03:24
---
Recorded finish-order dependency on OOMPAH-831. This does not block ongoing implementation, but OOMPAH-843 must not integrate before O831's complete f3b8326ed -> 93b0295bc security sequence is landed and its commits are replayed onto the reachable target lineage.
---
author: oompah
created: 2026-08-06 03:39
---
Withdrawing this implementation attempt before cutover. Independent review found acceptance blockers in backend-wide timeout wiring, startup feasibility validation, fail-closed configuration, alert/prompt behavior, and test assertions/diff hygiene. Preserve the worktree; repair after restart and after OOMPAH-831's ordered security commits are reachable.
---
author: oompah
created: 2026-08-06 03:39
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 146, Tool calls: 63
- Tokens: 1.2K in / 294 out [1.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 57m 57s
- Log: OOMPAH-843__20260806T024208Z.jsonl
---
author: oompah
created: 2026-08-06 07:10
---
Independent static review ACCEPTED rebased head 434081feff8b99c07b7d7d6d7a15bc577e61c488 with no blockers. The review traced the OOMPAH-831 conflict resolutions and confirmed submission/inspection plus project-aware validation semantics are both retained across API and ACP backends, with proportionate coverage. No tests were run; focused validation is queued behind the active authoritative exact gate.
---
author: oompah
created: 2026-08-07 20:52
---
Exact composition candidate ae92d0ee89a163b70a15d39003617529f66b455b is pushed on origin/OOMPAH-843 atop required OOMPAH-831 lineage base 0e0056375918977c9b0b2d59524ce8ae68ceee40. Validation: 42 deadline regressions and 1,659 broad focused tests passed; compile/static/diff checks green; independent exact-head review ACCEPT; remote parity 0/0 and clean. Holding for composition through epic OOMPAH-763, not a standalone main PR.
---
author: oompah
created: 2026-08-08 03:44
---
Recovered an unpublished worktree checkpoint after worker/service interruption. Exact recovery evidence is durable at refs/oompah/recovery/OOMPAH-843-75b61d327052be8a (98517d4c018bb511beaf5bdd1360f887f3c79386); the ownerless task was returned to Open.
---
author: oompah
created: 2026-08-08 03:44
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-08 03:44
---
Focus: Security Auditor
---
author: oompah
created: 2026-08-08 03:55
---
**Understanding (Security Auditor Review)**

Beginning security audit of OOMPAH-843 implementation for per-target deadlines and validation contract feasibility.

**Scope Reviewed So Far**:
1. Project model additions (oompah/models.py):
   - New fields: auditor_validation_target_deadlines (dict[str, int])
   - New field: auditor_validation_target_expected_seconds (dict[str, int])
   - Validation in from_dict: targets validated for ASCII alphanumeric + '_.-', no duplicates
   - Deadlines validated as positive integers, restricted to configured targets
   - Serialization/deserialization with proper redaction in to_safe_dict

**Key Security Vectors to Investigate**:
1. Shell injection prevention for Make targets - validate execution safety
2. Deadline enforcement at runtime - check api_agent.py and acp_backends
3. Configuration error handling - does fail-closed behavior work correctly?
4. Multi-project isolation - are deadlines properly scoped per project?
5. Validation-resource lease interaction - does deadline validation respect queuing delays?

**Next Steps**: Review auditor.py, api_agent.py, and acp_backends for runtime enforcement and attack surface.
---
author: oompah
created: 2026-08-08 04:02
---
**Security Audit Complete - PASS**

Reviewed implementation of per-target auditor validation deadlines with focus on security implications.

**ATTACK SURFACE ANALYSIS:**
1. Shell Injection Prevention ✅
   - Make targets properly escaped via re.escape() before regex use
   - Token validation enforces exact 'make' command + 1 target (case-sensitive)
   - No argument injection possible after target name
   - Tests: test_focused_make_target_must_be_explicit_and_exact (4 variants pass)

2. Path Escape Protection ✅
   - _AUDITOR_PATH_ESCAPE_RE catches absolute paths, parent traversal (..), home dirs
   - Newline filtering prevents command separators
   - shlex tokenization properly handles punctuation characters
   - Tests: test_read_only_fallback_validation_fails_closed_and_consumes_fatal_budget (8 path variants)

3. Credential File Access ✅  
   - _AUDITOR_SECRET_PATH_RE explicitly blocks .env, .git/config, SSH keys, certificates
   - All path checks run BEFORE contract matching (defense-in-depth)
   - Tests: test_read_only_fallback_validation_fails_closed_and_consumes_fatal_budget confirms .env blocking

4. Configuration Validation ✅
   - Project.from_dict() validates auditor_validation_targets: ASCII alphanumeric + '_.-', no duplicates
   - auditor_validation_target_deadlines must be positive integers only
   - Deadlines can only be configured for approved targets (not arbitrary values)
   - Tests: test_project_load_rejects_malformed_validation_configuration (4 scenarios pass)

5. Fail-Closed Behavior ✅
   - Configuration errors prevent command execution (not silent fallback)
   - Per-target deadline resolution returns errors on any incompatibility
   - Tests: test_configuration_error_prevents_api_command_execution, test_oompah_796_is_rejected_before_launch_when_gate_cannot_finish

6. Multi-Project Isolation ✅
   - Deadlines strictly scoped per project
   - No cross-project bleed in deadline resolution
   - Tests: test_contract_isolated_by_project, test_all_acp_catalogs_apply_the_same_project_target_deadline

7. Timeout Enforcement Chain ✅
   - API agent: _resolve_run_command_timeout_with_target() → resolve_auditor_validation_budget()
   - ACP agent: build_tool_catalog → _auditor_run_command_options() → resolve_auditor_validation_budget()
   - Timeout passed to _exec_run_command with subprocess.Popen(timeout=...)
   - Tests: test_api_agent_uses_target_deadline_even_with_eager_global_timeout, test_true_validation_overrun_is_terminated_at_target_deadline

**OWASP Coverage:**
- Injection (A03): Blocked via regex escaping, token validation, shlex safety checks
- Broken Access Control (A01): Project isolation, target allowlist enforcement
- Sensitive Data Exposure (A02): Credential file regex, path traversal prevention
- Configuration Issues (A05): Validation at Project.from_dict(), startup checks

**VERDICT:**  42 deadline tests PASS, 56 auditor contract tests PASS. Security posture is solid. Per-target deadlines properly integrated across API and ACP backends without introducing new vulnerabilities.
---
author: oompah
created: 2026-08-08 04:03
---
Security audit complete: Per-target auditor validation deadlines properly implemented with strong security controls. Shell injection prevention via regex escaping, path escape detection, credential file blocking, fail-closed configuration validation, and proper timeout enforcement across API and ACP backends. 42 deadline tests + 56 auditor contract tests pass. Ready for integration.
---
author: oompah
created: 2026-08-08 04:03
---
⚠️ **Late mutations after submission acceptance** (ae92d0ee vs ae92d0ee)

Changes appeared in the worktree after the submission was accepted but before cleanup completed. These late changes have been durably preserved and are available for the next retry.

**Recovery checkpoint:** `refs/oompah/recovery/OOMPAH-843-75b61d327052be8a` (snapshot: `98517d4c`)

The task has been reopened with the recovery context preserved. A new agent can review the changes and explicitly resubmit if needed.
---
author: oompah
created: 2026-08-08 04:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-08 04:04
---
Focus: Security Auditor
---
author: oompah
created: 2026-08-08 04:05
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-08 04:05
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 53s
- Log: OOMPAH-843__20260808T040445Z.jsonl
---
author: oompah
created: 2026-08-08 04:05
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-08 04:05
---
Focus: Security Auditor
---
author: oompah
created: 2026-08-08 04:06
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 20s (attempt #2)
---
author: oompah
created: 2026-08-08 04:06
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 46s
- Log: OOMPAH-843__20260808T040555Z.jsonl
---
author: oompah
created: 2026-08-08 04:07
---
Retrying (attempt #2, agent: standard)
---
author: oompah
created: 2026-08-08 04:07
---
Focus: Security Auditor
---
author: oompah
created: 2026-08-08 04:09
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Project-owner reconciliation: composed OOMPAH-843 repair a1917e770 is an ancestor of published e74449e4. Its exact review was accepted, 1,659 broad focused tests plus 42 deadline regressions passed, and the exact parent full gate passed 17,860 tests with zero failures; the later reopen was stale recovery churn for the same accepted head.
---
author: oompah
created: 2026-08-08 04:10
---
Run #3 [attempt=3, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 17
- Tokens: 36 in / 355 out [391 total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 16s
- Log: OOMPAH-843__20260808T040709Z.jsonl
---
author: oompah
created: 2026-08-08 04:10
---
Published and validated in epic-OOMPAH-763 at e74449e4f9303f35c2cc2c1c5fc78ee979f4d268.
---
<!-- COMMENTS:END -->
