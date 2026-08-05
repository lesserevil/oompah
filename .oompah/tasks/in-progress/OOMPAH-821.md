---
id: OOMPAH-821
type: task
status: In Progress
priority: null
title: Align terminal-audit recovery alerts with retryable mixed-attempt histories
parent: OOMPAH-770
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T05:11:56.700024Z'
updated_at: '2026-08-05T05:40:41.390445Z'
work_branch: epic-OOMPAH-770--task-OOMPAH-821
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f6373ef564f02957e54284145b83350868b90fdca9864b8366cebc41a8abb7ba
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T05:39:01.613934+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-770, OOMPAH-795, and OOMPAH-796 address broader\
    \ liveness and alert architecture; none specifically covers terminal-audit retry\
    \ eligibility for mixed attempt histories or recovery-command parity.\nFocus handoff:\
    \ duplicate_detector  \nDuplicate preflight verdict: no_duplicate  \nMatches:\
    \ none  \n\nEvidence: OOMPAH-770, OOMPAH-795, and OOMPAH-796 address broader liveness\
    \ and alert architecture; none specifically covers terminal-audit retry eligibility\
    \ for mixed attempt histories or recovery-command parity."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: b06321d7-2501-4d86-bd80-ccc6baf2e6ad
oompah.work_branch: epic-OOMPAH-770--task-OOMPAH-821
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-770--task-OOMPAH-821
  base_branch: epic-OOMPAH-770
  base_sha: f1e7925b7263f980517f943291102c8c83335ed2
  updated_at: '2026-08-05T05:39:46.973498+00:00'
oompah.task_costs:
  total_input_tokens: 46470
  total_output_tokens: 272
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46470
      output_tokens: 272
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46470
    output_tokens: 272
    cost_usd: 0.0
    recorded_at: '2026-08-05T05:39:01.604420+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-821__20260805T053846Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-770--task-OOMPAH-821
    source_sha: f1e7925b7263f980517f943291102c8c83335ed2
    completed_at: '2026-08-05T05:39:01.682857+00:00'
---
## Summary

Live regression: OOMPAH-745 is integrated at exact head b08a12057afed4e7af5080e7e47522eed16dc2ce and its terminal-audit chain completed in no_auditor after earlier abandoned/finalization-failure attempts. The integration sweep emits terminal_audit_recovery guidance telling an owner to rearm, but both supported owner commands are rejected with HTTP 409 'No matching exhausted audit': evidence-addendum rearm is correctly limited to missing_evidence, while infrastructure rearm currently requires every historical attempt classification to be NO_AUDITOR/INFRASTRUCTURE_ERROR/POLICY_INCOMPATIBILITY. The task remains Ready to Integrate with an integrated queue row and a permanent actionable warning despite exact-head focused verification.\n\nImplementation scope: make the sweep/recovery classifier and TerminalTransitionCoordinator.retry_failed_audit share one canonical retry-eligibility decision; classify retryability from the terminal exhaustion outcome while preserving prior attempt history, or suppress/replace the alert with truthful supported action when a mixed chain is not retryable. Ensure same-head integration reflow cannot move an exhausted task into a state where the advertised recovery command is rejected. Preserve owner authentication, exact evidence fingerprint fencing, independent-auditor requirements, successful-audit finality, and evidence-addendum restriction to missing_evidence. Relevant files: oompah/terminal_transition_coordinator.py, oompah/orchestrator.py recovery alert/completion sweep, oompah/server.py error mapping, task CLI/operator docs if guidance changes.\n\nRequired tests: reproduce OOMPAH-745 with abandoned + finalization_failure + terminal no_auditor attempts, same-head integrated reflow, emitted alert, owner infrastructure retry, fresh pending audit, and alert clearing; prove alert/action parity for every supported terminal failure classification; prove missing-evidence still requires a current-fingerprint successful-check addendum; prove non-owner, changed fingerprint, successful completed audit, and repeated retry remain rejected/coalesced as appropriate; cover restart/sweep races without warning spam. Acceptance: every emitted terminal_audit_recovery action succeeds against the same durable snapshot or the UI gives a truthful non-retry action; OOMPAH-745 can re-enter independent audit without terminal override; focused coordinator/server/integration/observability tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 05:38
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 05:38
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 05:39
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.5K in / 272 out [46.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 42s
- Log: OOMPAH-821__20260805T053846Z.jsonl
---
author: oompah
created: 2026-08-05 05:39
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-05 05:39
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-05 05:40
---
Understanding: This issue addresses a regression where terminal-audit recovery alerts emit retry guidance that is then rejected with HTTP 409. The root cause: the sweep/recovery classifier and TerminalTransitionCoordinator.retry_failed_audit have different retry-eligibility logic. When a task has mixed-attempt history (abandoned + finalization_failure + terminal no_auditor), infrastructure rearm incorrectly requires ALL historical attempts to be retryable classifications, while the alert was emitted based on the terminal state alone. 

Planned approach: 
1. Identify the divergence between sweep recovery classifier and retry_failed_audit logic
2. Create canonical retry-eligibility decision based on terminal exhaustion outcome
3. Align alert emission with actual supported retry actions
4. Add comprehensive tests for mixed-attempt scenarios
5. Ensure alert/action parity for all terminal failure classifications

Relevant files: terminal_transition_coordinator.py, orchestrator.py, server.py
---
<!-- COMMENTS:END -->
