---
id: TASK-379
title: 'WebhookForwarder no-ops: gh-webhook extension missing and --events flag absent'
status: Done
assignee: []
created_date: 2026-05-05 19:35
updated_date: 2026-05-05 19:49
labels:
- merged
- bug
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: bug
beads:
  id: oompah-zlz_2-2g1
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-zlz_2-2g1
  target_branch: null
  url: null
  created_at: '2026-05-05T19:35:36Z'
  updated_at: '2026-05-05T19:49:07Z'
  closed_at: '2026-05-05T19:49:07Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
WebhookForwarder spawns `gh webhook forward --url <url>` for each project, logs "WebhookForwarder: started gh webhook forward for project <name> (pid=<N>)", and considers itself running. In reality the subprocess exits immediately on this machine because:

1. `gh webhook` is a third-party extension (cli/gh-webhook), not a built-in `gh` command. On a clean machine without `gh extension install cli/gh-webhook`, every spawn fails silently.

2. Even when the extension IS installed, the current invocation in oompah/webhooks.py:510-519 omits the `--events` flag. Per the extension's docs, that means no events are actually subscribed/forwarded.

Net effect: zero forge webhook events ever reach oompahs _handle_webhook_event. Auto-merge label updates, push-driven source sync (commit f6c00a5), and all PR/push reactions go through the 2-min full-sync safety net instead of the intended near-realtime webhook path.

Confirmed today by `ps -ef | grep "gh webhook" | grep -v grep` returning empty while WebhookForwarder log lines claim it is running, and by `gh webhook --help` returning "unknown command".
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df9a4-a8fe-7747-97b6-20307e31ac6e
author: oompah
created: 2026-05-05T19:36:51Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9a4-cf59-7f1b-af01-7b75468605ca
author: oompah
created: 2026-05-05T19:37:01Z

Focus: Technical Writer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9a6-b288-7320-a3a6-385d222150de
author: oompah
created: 2026-05-05T19:39:05Z

Understanding: WebhookForwarder spawns 'gh webhook forward' but (1) the gh-webhook extension isn't installed by default so the subprocess exits silently and (2) the invocation is missing --events. Plan: (a) Detect 'gh webhook' availability once at startup; log a single ERROR and skip launching when missing. (b) Add --events push,pull_request to the invocation. (c) Capture stderr and log it on subprocess exit. (d) Surface forwarder-down state via the existing orchestrator _alerts mechanism (already plumbed to dashboard). (e) Add a 'make install-gh-extensions' target that runs 'gh extension install cli/gh-webhook' idempotently. (f) Update test_webhooks.py with cases for missing extension, --events flag, and stderr capture. Documentation: update README/docs section on webhook setup.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9ae-f534-7df2-9144-10a242f61281
author: oompah
created: 2026-05-05T19:48:06Z

Discovery: WebhookForwarder.start() never probed for the gh-webhook extension and _launch() omitted --events. The orchestrator already had an _alerts list that the dashboard renders as a banner, so wiring forwarder-down state through that list was the cleanest path.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9af-246f-75c8-82c3-3ef4c7013bcf
author: oompah
created: 2026-05-05T19:48:18Z

Implementation: (1) Added check_gh_webhook_available() one-shot probe (gh webhook --help) called from WebhookForwarder.start(); logs a single ERROR when missing and sets _extension_available=False. (2) _launch() now passes --events push,pull_request (configurable via OOMPAH_WEBHOOK_EVENTS) and skips silently when the extension is unavailable (no per-cycle log spam). (3) Added _drain_stderr() background task that captures the subprocess's stderr tail and logs it at WARNING when the process exits non-zero, surfacing auth/install errors in oompah.log. (4) Added status_callback hook; __main__.py wires it to orchestrator._alerts so the dashboard shows a 'Webhooks degraded' banner. (5) Added 'make install-gh-extensions' Makefile target — idempotent, runs gh extension install cli/gh-webhook only when missing. (6) Wrote docs/webhook-forwarding.md covering architecture (mermaid diagram), setup, verification, configuration, and troubleshooting; linked from README features list.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9af-4eef-71e0-a666-c123fba5f0ed
author: oompah
created: 2026-05-05T19:48:29Z

Verification: full test suite passes (1327 passed). Added 13 new tests in tests/test_webhooks.py covering: extension probe (gh missing, available, missing returns stderr); --events flag in argv (default, init param, env var override); skip-when-unavailable; one-shot ERROR (not per-cycle); status_callback availability transitions; status property snapshot; stderr drainer; _terminate cancels stderr task. Also verified 'make install-gh-extensions' is idempotent — first run installs cli/gh-webhook, second run reports already installed.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9af-dbeb-7a60-9459-a8c3f027c5fa
author: oompah
created: 2026-05-05T19:49:05Z

Completion: Pushed to origin/oompah-zlz_2-2g1 (commit 7ba09ea). Delivered:
- oompah/webhooks.py: check_gh_webhook_available() probe, --events flag, stderr capture, status_callback, _drain_stderr/_cancel_stderr_task helpers
- oompah/__main__.py: wires forwarder status -> orchestrator._alerts (dashboard banner)
- Makefile: install-gh-extensions idempotent target
- docs/webhook-forwarding.md: full setup/verify/troubleshoot guide with mermaid diagram
- README.md: feature bullet linking to the new doc
- tests/test_webhooks.py: +13 tests covering all AC bullets

All 1327 tests pass. AC items satisfied:
1. Startup detection of gh webhook ✓ (check_gh_webhook_available + single ERROR + skip)
2. --events passed when launching ✓ (default push,pull_request, configurable)
3. Stderr captured/logged ✓ (_drain_stderr + WARNING on non-zero exit)
4. Dashboard degraded-mode banner ✓ (status_callback -> orchestrator._alerts)
5. make install-gh-extensions ✓ (idempotent, verified locally)
6. Tests for missing-extension skip and --events presence ✓
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9af-ef14-7468-b4a3-7c19c86576c8
author: oompah
created: 2026-05-05T19:49:10Z

Agent completed successfully in 739s (4557881 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
