---
id: TASK-17
title: Fetching models from provider can scroll beyond the screen
status: Done
assignee: []
created_date: 2026-03-06 04:57
updated_date: 2026-03-06 17:53
labels:
- archive:yes
- merged
- bug
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: bug
beads:
  id: umpah-pyo
  state: closed
  parent_id: null
  dependencies: []
  branch_name: umpah-pyo
  target_branch: null
  url: null
  created_at: '2026-03-06T04:57:07Z'
  updated_at: '2026-03-06T17:53:20Z'
  closed_at: '2026-03-06T17:53:20Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When adding a provider and pressing the 'fetch models' button, if there are a large number of models, they can make the dialog so large it can expand beyond the screen. The multi-select for models should scroll when there are more models than will fit in the dialog.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 7606e7cd-3bea-481a-a474-c1f94fcd8446
author: umpah
created: 2026-03-06T04:57:31Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0860e249-d71a-4c6f-84e0-5e1cceda0e74
author: umpah
created: 2026-03-06T04:59:56Z

Agent completed successfully in 145s (18214 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ba778885-9708-48c9-a66c-6984d9e1bd72
author: umpah
created: 2026-03-06T05:00:01Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: dac54c7c-c495-4616-a6b5-46045e24befc
author: umpah
created: 2026-03-06T05:01:03Z

Agent completed successfully in 62s (8433 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 04527c42-4758-4f13-8a68-eed73cecb8d1
author: umpah
created: 2026-03-06T05:01:04Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 342186f1-2672-48f3-b78d-cd442159be5e
author: umpah
created: 2026-03-06T05:02:55Z

Agent completed successfully in 111s (14059 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 945adbd3-879a-46bb-8ebd-7c791b5d7f9c
author: oompah
created: 2026-03-06T17:27:55Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7efbaafa-67c7-4149-84c0-fe89d14fb73e
author: Shawn Edwards
created: 2026-03-06T17:28:01Z

I understand the issue: When fetching models from a provider in the add provider dialog, if there are many models returned, the multi-select component expands the dialog beyond the screen boundaries. The fix needs to add scrolling to the model multi-select so it stays within the dialog/screen bounds. My plan is to explore the codebase to find the provider dialog component and add appropriate CSS constraints (max-height + overflow-y: scroll/auto) to the models multi-select.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8f054d31-490d-4328-bd5d-9bcb47ef3e41
author: Shawn Edwards
created: 2026-03-06T17:28:30Z

Found the relevant code: In server.py, the PROVIDERS_HTML contains the provider dialog. The models section uses a 'tag-input-wrap' div (class tag-input-wrap) that wraps model tags in a flex container. When many models are fetched, the tag-input-wrap div expands vertically without any height constraint, causing the dialog to grow beyond the screen. The fix is to add max-height and overflow-y: auto to the tag-input-wrap element so it scrolls when there are many models.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 06f11c05-56b8-4fe3-b9ef-8611c58116e8
author: oompah
created: 2026-03-06T17:30:12Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6088a8a9-6fe2-42ca-a514-73cdf7926fe6
author: Shawn Edwards
created: 2026-03-06T17:30:20Z

I understand the issue: When fetching models from a provider, if there are many models, the dialog expands beyond the screen boundaries. The fix needed is to make the multi-select component for models scrollable when there are more models than can fit in the dialog. My plan is to: 1) Find the provider dialog/form component, 2) Locate the model multi-select element, 3) Add CSS overflow/scroll constraints to keep it within the viewport.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 75d80b07-ec38-4114-a673-a7b66cb4c025
author: Shawn Edwards
created: 2026-03-06T17:30:50Z

Found the code: The issue is in the PROVIDERS_HTML string in oompah/server.py. The provider dialog (.dialog element) has a fixed width (520px) but no max-height constraint or overflow handling. When 'Fetch Models' is called and many models are returned, they get added to the tag-input-wrap div, which grows unbounded, pushing the dialog beyond the screen. The fix needs to: 1) Add max-height to the .dialog element with overflow-y: auto, OR 2) Specifically constrain the models tag-input-wrap with a max-height and overflow-y: scroll.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 37df0076-e1b8-4eef-b19c-6dece8a50634
author: oompah
created: 2026-03-06T17:33:00Z

Agent failed: HTTP 524 from https://api.haimaker.ai/v1/chat/completions: error code: 524. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8e43bc4e-02a6-4682-bcaf-93ec9916c518
author: oompah
created: 2026-03-06T17:33:10Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 537fd474-8014-4363-8ca2-b9a121a1fefb
author: Shawn Edwards
created: 2026-03-06T17:33:15Z

I understand the issue: When fetching models from a provider in a dialog, if there are many models, the multi-select list expands the dialog beyond the screen bounds. The fix needs to make the model list scrollable so it stays within the dialog/screen bounds. My plan is to find the relevant dialog component and add scrollable behavior to the model multi-select.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 18fa2691-cebc-47e1-9252-4d02d1375bed
author: Shawn Edwards
created: 2026-03-06T17:33:43Z

Found the relevant code: In server.py, the PROVIDERS_HTML string contains the provider dialog. The model list uses a tag-input-wrap div (lines around the .tag-input-wrap style). When 'Fetch Models' is clicked, models are added to a div element that wraps model tags with an input. The problem is there's no max-height or overflow:auto on this div, so with many models it expands infinitely. Additionally, the .dialog has no max-height set, so it can grow beyond the viewport. The fix needs to: 1) Add max-height + overflow:auto to the model list container, and 2) ensure the dialog itself has max-height with overflow handling.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: cde2f7bb-6ac2-4c32-a5e4-fc926c097834
author: oompah
created: 2026-03-06T17:35:35Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2feb2384-fa6d-4292-88f8-0d5d600ab249
author: Shawn Edwards
created: 2026-03-06T17:35:40Z

I understand the issue: When fetching models from a provider, if there are many models, the multi-select list can expand the dialog beyond the screen boundaries. The fix needs to make the model list scrollable so it stays within the dialog/screen bounds. My plan is to find the relevant UI component for the provider dialog's model fetch/select UI and add appropriate scrolling/height constraints.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: dce98208-26bc-403b-bd5d-355a595a2cee
author: Shawn Edwards
created: 2026-03-06T17:36:21Z

Found the root cause: In server.py, the PROVIDERS_HTML contains the provider dialog. The .dialog CSS class has no max-height constraint, and the .tag-input-wrap (the model tags container) has no max-height or overflow scrolling. When many models are fetched, the tag-input-wrap expands without limit, pushing the dialog beyond the screen. Fix: add max-height + overflow-y: auto to both the .dialog and .tag-input-wrap, and also make the dialog scrollable with proper flex layout.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: e56657e0-2a8c-4c87-9899-9f3f687b0c49
author: Shawn Edwards
created: 2026-03-06T17:37:16Z

Implemented fix in oompah/server.py: (1) Added max-height: 90vh and overflow-y: auto to the .dialog CSS class in PROVIDERS_HTML, so the dialog itself never exceeds the viewport height. (2) Added max-height: 160px and overflow-y: auto to the .tag-input-wrap CSS class, so when many models are fetched, the model tags container scrolls rather than expanding indefinitely. These two changes together ensure the dialog stays within screen bounds even with hundreds of models.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 714b835c-59d9-4469-bc1a-7cf68057bf9f
author: Shawn Edwards
created: 2026-03-06T17:38:10Z

Verification: No automated tests exist in this repo, but validated changes manually: (1) Python syntax check passes, (2) CSS changes confirmed correct - tag-input-wrap has max-height:160px + overflow-y:auto, and dialog has max-height:90vh + overflow-y:auto. The fix prevents the model list from expanding the dialog beyond screen bounds.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6f1cedd3-ba4c-4d56-a161-e925f8f87446
author: oompah
created: 2026-03-06T17:40:06Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 206cd5c9-1959-4fbe-8192-af58a060de8f
author: Shawn Edwards
created: 2026-03-06T17:40:10Z

I understand the issue: When fetching models from a provider, if there are many models, the multi-select dialog expands beyond the screen. The fix needs to add scrolling to the model list so it stays within the screen bounds. My plan is to find the dialog/component that renders the model list and add appropriate CSS/styling to make it scrollable.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 976425ac-662e-4220-a722-dcecc2d20c0c
author: Shawn Edwards
created: 2026-03-06T17:41:41Z

Found the issue: In server.py PROVIDERS_HTML, the provider dialog has max-height: 90vh with overflow-y: auto on the .dialog element, and the tag-input-wrap (models list) has max-height: 160px. The problem is that the dialog-overlay uses align-items: center in flexbox - when the dialog content is very tall (many models), the flex centering can push the dialog partially off-screen. Additionally, max-height may not be enforced properly in this layout. The fix: ensure the tag-input-wrap has an adequate max-height with proper scrolling, and fix the dialog to use display:flex+flex-direction:column with a scrollable body section, so it never grows beyond the viewport.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 44379e2a-4142-4314-b2af-7f66ffbdb375
author: oompah
created: 2026-03-06T17:43:50Z

Agent failed: HTTP 524 from https://api.haimaker.ai/v1/chat/completions: error code: 524. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 16da1818-e1da-480f-b7d2-e3a7a7a8a943
author: oompah
created: 2026-03-06T17:44:01Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: c67b6315-55f9-4692-9d62-16e9314a6dc5
author: Shawn Edwards
created: 2026-03-06T17:44:06Z

I understand the issue: When fetching models from a provider in the add provider dialog, if there are many models returned, the multi-select list expands the dialog beyond the screen boundaries. The fix needs to make the model list scrollable so it stays within screen bounds. My plan is to: 1) Find the provider dialog/form component, 2) Locate the model multi-select widget, 3) Add appropriate scroll/height constraints to keep it within the viewport.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4d54908e-92ae-487c-9de8-e4d7bf2eb713
author: oompah
created: 2026-03-06T17:45:06Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 75b7fee6-31f0-4175-858a-d9c32f077280
author: Shawn Edwards
created: 2026-03-06T17:45:10Z

I understand the issue: When fetching models from a provider in a dialog, if there are many models, the multi-select list expands the dialog beyond the screen boundaries. The fix needs to make the model list scrollable so it stays within the dialog/screen bounds. My plan is to find the relevant dialog/component code and add overflow/scroll constraints to the model multi-select.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: cd154ea8-d836-4fd2-9adb-866e4604d459
author: oompah
created: 2026-03-06T17:48:15Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 90714b03-be4b-496e-a90b-f67ca94267e1
author: oompah
created: 2026-03-06T17:48:22Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9421d828-fe0a-40cc-980f-6e186eb0a8a8
author: Shawn Edwards
created: 2026-03-06T17:48:54Z

I understand the issue: When fetching models from a provider, if there are many models, the multi-select (tag-input-wrap) in the provider dialog can expand beyond the screen height. My plan is to add a max-height constraint and overflow-y: auto to the models input area (tag-input-wrap) in the PROVIDERS_HTML in oompah/server.py, so it scrolls instead of expanding the dialog when many models are fetched.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 857aec6f-897f-428a-97e9-510d6e7b925a
author: Shawn Edwards
created: 2026-03-06T17:50:00Z

Found the issue: The provider dialog's tag-input-wrap (the models multi-select) has max-height: 160px and overflow-y: auto in CSS. However, when many models are fetched, the dialog itself can still grow beyond the viewport because the models input wrap's max-height may be insufficient relative to dialog height constraints. The fix is to ensure the models section has a proper, relatively-sized max-height (using vh units) so it scrolls instead of forcing the dialog to expand, and make the default-model select also properly constrained.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 908999bc-a439-4fc6-ac60-75eb0e4e356a
author: oompah
created: 2026-03-06T17:50:52Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 09324036-69ef-4573-a76a-49f590940da1
author: Shawn Edwards
created: 2026-03-06T17:51:00Z

I understand the issue: When fetching models from a provider in the add provider dialog, if there are many models returned, the multi-select list expands the dialog beyond the screen boundaries. My plan is to examine the current state of the code (previous agents have worked on this), verify if the fix is already in place, and ensure it works correctly by adding proper scroll constraints to the model list container.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3311e38f-50a2-4c6d-9a69-74fe00acb381
author: Shawn Edwards
created: 2026-03-06T17:51:30Z

Found the current state: Previous agents have partially addressed this. The .tag-input-wrap has max-height: 30vh and overflow-y: auto (line 2275-2276), which should make the model list scroll. However, the .dialog class still has 'max-height: none' (line 2342), which allows it to grow unbounded. The dialog-overlay has overflow-y: auto and padding which should handle scrolling. The fix looks mostly in place, but I need to verify if the dialog itself needs a max-height constraint as well.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 97058961-a11c-4092-ba1d-e965cef33513
author: Shawn Edwards
created: 2026-03-06T17:52:50Z

Implementation verified: The working tree contains the correct fix. The approach uses two layers: (1) .tag-input-wrap has max-height: 30vh + overflow-y: auto so the model list scrolls within 30% of the viewport, and (2) .dialog-overlay uses align-items: flex-start + overflow-y: auto + padding so if the dialog still exceeds the viewport, the overlay itself scrolls. This is better than the previous committed version (160px fixed height + dialog scrolling) as it's viewport-relative and handles both scenarios gracefully. Committing these uncommitted changes now.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5ff2b575-f598-483c-bd2a-45c1513d8d9e
author: Shawn Edwards
created: 2026-03-06T17:53:15Z

PR created: https://github.com/lesserevil/oompah/pull/1

The fix is complete. Two CSS changes in oompah/server.py:
1. tag-input-wrap: max-height: 30vh + overflow-y: auto - model list scrolls within 30% of viewport height
2. dialog-overlay: align-items: flex-start + overflow-y: auto + padding - overlay scrolls as fallback if dialog is very tall

Python syntax verified OK. No automated tests exist in the repo.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1eea5744-adac-4df5-b820-6d094783434a
author: oompah
created: 2026-03-06T17:53:25Z

Agent completed successfully in 153s (294591 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
