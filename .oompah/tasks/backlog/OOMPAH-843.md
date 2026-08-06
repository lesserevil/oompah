---
id: OOMPAH-843
type: task
status: Backlog
priority: null
title: Make auditor validation targets and command deadlines mutually feasible
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T02:39:33.484875Z'
updated_at: '2026-08-06T02:39:33.484875Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live OOMPAH-796 audit attempt attempt-bf484b85b4ed on 2026-08-06 exposed an impossible validation contract. The auditor correctly requested the focused Make target for the workflow domain, but policy rejected it because only make test, make test-serial, and make check-secrets were configured. It then ran permitted make test, which the agent command wrapper killed at the default 720-second deadline even though this repository's canonical full suite consistently needs roughly 1,080 seconds. The auditor next selected slower make test-serial, guaranteeing another timeout and consuming its bounded session without verdict evidence.\n\nImplementation scope:\n- Validate at project load/startup that every configured auditor validation target has a command deadline compatible with its observed/configured gate budget; fail closed with a truthful configuration action instead of launching an impossible audit.\n- Allow project-scoped focused Make targets required by the audited domain while preserving the exact allowlist, no arbitrary shell expansion, read-only authority, secret redaction, and validation-resource serialization.\n- Derive or configure per-target deadlines rather than applying one shorter global default to every permitted target; queued validation time must not consume execution time.\n- Teach the auditor prompt/tool response to prefer compatible focused targets and not fall back from a timed-out parallel full suite to a predictably slower serial suite.\n- Preserve independent verdict requirements and classify an impossible validation contract separately from provider transport failure or code failure.\n\nRelevant code: oompah/api_agent.py run-command deadline resolution, oompah/acp_tools.py command execution, oompah/auditor.py validation-target contract/prompt, project configuration and .env.example, validation-resource lease/liveness reporting.\n\nRequired tests:\n- A configured full target with expected duration above 720 seconds receives a compatible deadline and completes; true overruns remain bounded.\n- A domain-focused Make target is permitted only when explicitly configured for that project and remains shell-safe.\n- Auditor queued behind an exact gate retains its full execution budget after acquisition.\n- Reproduce OOMPAH-796: focused target denied plus 1,080-second full target under a 720-second default must fail configuration before launch or choose a feasible target, never loop into test-serial.\n- Multi-project targets/deadlines stay isolated; invalid targets, mutation, redirection, and credential access remain fatal.\n\nAcceptance criteria:\n- Every advertised auditor validation command can finish within its effective execution budget under the project's configured gate duration.\n- No auditor burns an attempt cycling through targets that are structurally unable to finish.\n- State and alerts identify configuration incompatibility with the exact target/deadline evidence.\n- Focused auditor/ACP/liveness/validation-resource/config tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

