---
id: TASK-354
title: Implement adaptive polling with webhook health check
status: Done
assignee: []
created_date: 2026-05-05 03:45
updated_date: 2026-05-05 17:06
labels:
- merged
- beads-migrated
dependencies:
- TASK-353
- TASK-352
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-zlz_2-vt9
  state: closed
  parent_id: oompah-zlz_2-1a7
  dependencies:
  - oompah-zlz_2-blg
  - oompah-zlz_2-yed
  branch_name: oompah-zlz_2-vt9
  target_branch: null
  url: null
  created_at: '2026-05-05T03:45:35Z'
  updated_at: '2026-05-05T17:06:18Z'
  closed_at: '2026-05-05T17:06:18Z'
parent: TASK-329
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Modify the polling loop in orchestrator.py (around lines 1021/1049) to: (1) check per-project webhook health using the last_webhook_received_at timestamp, (2) skip or delay polling for projects with recent webhook deliveries (within last 2-3 minutes), (3) fall back to 2-minute polling for projects with stale/missing webhook deliveries. Add a helper function is_webhook_healthy(project_id) that checks if last delivery is recent enough.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df83c-d2e9-7635-8640-e0a53d518437
author: oompah
created: 2026-05-05T13:03:49Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df83c-f4f6-7c44-89e6-e43aad145fa1
author: oompah
created: 2026-05-05T13:03:58Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df843-7793-7265-8527-e5fd71388978
author: oompah
created: 2026-05-05T13:11:04Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df843-b733-74a3-8051-c27251dbe122
author: oompah
created: 2026-05-05T13:11:21Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df843-bbb8-7b7d-9531-df8be3514503
author: oompah
created: 2026-05-05T13:11:22Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df844-0510-7a1d-a3d6-553a00b6380d
author: oompah
created: 2026-05-05T13:11:41Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df844-6d76-70c3-84f3-6dfd6f95e0ea
author: oompah
created: 2026-05-05T13:12:07Z

Retrying (attempt #2, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df844-7701-7659-9efb-c885f929806b
author: oompah
created: 2026-05-05T13:12:10Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df844-b8a7-7ea6-afa9-910be2d1d83b
author: oompah
created: 2026-05-05T13:12:27Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 40s (attempt #3)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df845-824c-7e0d-81cf-d73c20a5bb08
author: oompah
created: 2026-05-05T13:13:18Z

Retrying (attempt #3, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df845-868a-7be2-b67f-e80e5e125a8d
author: oompah
created: 2026-05-05T13:13:19Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df845-cac7-7cf0-8b09-c9be7d5f0e3f
author: oompah
created: 2026-05-05T13:13:37Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 80s (attempt #4)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df847-4ee7-776e-bb6e-1a205ff02b1e
author: oompah
created: 2026-05-05T13:15:16Z

Retrying (attempt #4, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df847-51c7-714f-a391-cdbebc6b1b2e
author: oompah
created: 2026-05-05T13:15:17Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df847-9aec-7449-b20f-aeaf939f36da
author: oompah
created: 2026-05-05T13:15:36Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 160s (attempt #5)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df84a-98ac-74e2-82e3-e28fcaf8aec4
author: oompah
created: 2026-05-05T13:18:52Z

Retrying (attempt #5, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df84a-9c7b-7e9a-a583-0b43c9246bdd
author: oompah
created: 2026-05-05T13:18:53Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df84a-defe-791f-921e-db45f7701054
author: oompah
created: 2026-05-05T13:19:10Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #6)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df84f-edbe-7bdb-91b1-f2d97e83fa14
author: oompah
created: 2026-05-05T13:24:41Z

Retrying (attempt #6, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df84f-fbe6-7762-9ec5-c8db6a5dfa0b
author: oompah
created: 2026-05-05T13:24:45Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df850-3d18-7956-9d7f-5afe8783572c
author: oompah
created: 2026-05-05T13:25:01Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #7)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df855-4947-7660-8dae-370deceef67b
author: oompah
created: 2026-05-05T13:30:32Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df855-694b-7714-92b2-2ed3240561cd
author: oompah
created: 2026-05-05T13:30:40Z

Retrying (attempt #7, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df855-921b-7269-98ef-174406dc9fdb
author: oompah
created: 2026-05-05T13:30:51Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #8)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df85a-7f2d-7aae-85f4-35a7d4d2829c
author: oompah
created: 2026-05-05T13:36:14Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df85a-a34e-7255-b435-e98f98b56ba2
author: oompah
created: 2026-05-05T13:36:23Z

Retrying (attempt #8, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df85a-c1c8-7762-b406-28b8695a94d0
author: oompah
created: 2026-05-05T13:36:31Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #9)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df85f-ac4d-7dd6-9efc-8755dff15142
author: oompah
created: 2026-05-05T13:41:53Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df85f-b58d-7c29-9964-f75209f281ab
author: oompah
created: 2026-05-05T13:41:55Z

Retrying (attempt #9, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df85f-ef37-7b08-9d53-2393594a4a42
author: oompah
created: 2026-05-05T13:42:10Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #10)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df864-d153-776a-9908-ac9e9dcbb6c8
author: oompah
created: 2026-05-05T13:47:30Z

Retrying (attempt #10, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df864-dcc2-7e34-bafa-cd7036b4b335
author: oompah
created: 2026-05-05T13:47:33Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df865-1fa3-717e-a9ab-9dfe525c749a
author: oompah
created: 2026-05-05T13:47:50Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #11)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df86a-085c-79fa-bab4-b7a5f8781508
author: oompah
created: 2026-05-05T13:53:12Z

Retrying (attempt #11, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df86a-1107-7e3c-b916-fd8b6dd66302
author: oompah
created: 2026-05-05T13:53:14Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df86a-529c-7d7d-9a32-e8d18244c3ad
author: oompah
created: 2026-05-05T13:53:31Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #12)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df86f-3916-7d0b-a5f0-4973eafdadd9
author: oompah
created: 2026-05-05T13:58:52Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df86f-41d0-7119-b19b-30b1971055c2
author: oompah
created: 2026-05-05T13:58:54Z

Retrying (attempt #12, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df86f-7b2c-7ecd-9727-a18bbe5cfde6
author: oompah
created: 2026-05-05T13:59:09Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #13)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df874-6fa0-7860-972d-6a0882240ca9
author: oompah
created: 2026-05-05T14:04:34Z

Retrying (attempt #13, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df874-7491-7ebd-94c2-9fd1e314eb65
author: oompah
created: 2026-05-05T14:04:35Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df874-b54d-7e19-9426-2a0b6d04a8bc
author: oompah
created: 2026-05-05T14:04:51Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #14)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df879-c863-7612-90e7-b377e4c1ee3f
author: oompah
created: 2026-05-05T14:10:24Z

Retrying (attempt #14, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df879-ccd7-7bbf-9cdf-ea216c312689
author: oompah
created: 2026-05-05T14:10:25Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df87a-0e8c-7e21-82c7-b2364adfc0b7
author: oompah
created: 2026-05-05T14:10:42Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #15)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df87e-f225-763d-a22e-10d2749d56b1
author: oompah
created: 2026-05-05T14:16:02Z

Retrying (attempt #15, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df87e-f5bd-72f9-bcf2-973a319121f6
author: oompah
created: 2026-05-05T14:16:03Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df87f-4502-7576-a31d-4ac5f376e472
author: oompah
created: 2026-05-05T14:16:24Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #16)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df884-36dd-718a-9b23-80306c6d27a5
author: oompah
created: 2026-05-05T14:21:48Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df884-427d-736b-8ac8-2bec10524078
author: oompah
created: 2026-05-05T14:21:51Z

Retrying (attempt #16, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df884-8af9-7d81-9a65-243c40da5313
author: oompah
created: 2026-05-05T14:22:09Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #17)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df889-966a-7537-92e5-3a28a10cb2c1
author: oompah
created: 2026-05-05T14:27:40Z

Retrying (attempt #17, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df889-a4be-7825-82a9-5338ff002710
author: oompah
created: 2026-05-05T14:27:43Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df889-eb3a-788b-be0d-354e7afbfb89
author: oompah
created: 2026-05-05T14:28:01Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #18)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df88f-1143-76fd-9fca-069402d971b9
author: oompah
created: 2026-05-05T14:33:39Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df88f-527c-7445-8da8-4362fd796ac9
author: oompah
created: 2026-05-05T14:33:56Z

Retrying (attempt #18, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df88f-5e3b-71d4-9702-df00d166f1a2
author: oompah
created: 2026-05-05T14:33:59Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #19)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df894-41fd-703a-b023-4baf5c4ae81b
author: oompah
created: 2026-05-05T14:39:19Z

Retrying (attempt #19, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df894-51ac-7ac5-8643-232eb2f0c784
author: oompah
created: 2026-05-05T14:39:23Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df894-984e-7269-acb6-063b73731bc4
author: oompah
created: 2026-05-05T14:39:41Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #20)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df899-7c8a-7a41-bed2-85ff1553c89c
author: oompah
created: 2026-05-05T14:45:02Z

Retrying (attempt #20, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df899-805e-7c9e-ab3b-06f337ff2bdc
author: oompah
created: 2026-05-05T14:45:03Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df899-c7f5-7c8e-a5ad-6e88a680eab7
author: oompah
created: 2026-05-05T14:45:21Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #21)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df89e-dd5f-77ef-98b2-75a47d315103
author: oompah
created: 2026-05-05T14:50:54Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df89e-e04b-79d7-ac02-58c2f12c8611
author: oompah
created: 2026-05-05T14:50:55Z

Retrying (attempt #21, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df89f-2299-7a7b-b264-f2c6190b2fa8
author: oompah
created: 2026-05-05T14:51:12Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #22)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8a4-0d7f-7874-a77c-497bd082fdb1
author: oompah
created: 2026-05-05T14:56:34Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8a4-1675-7c5c-95d7-7257654122c7
author: oompah
created: 2026-05-05T14:56:36Z

Retrying (attempt #22, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8a4-4e9b-76e1-9ae8-7aa7abde2a81
author: oompah
created: 2026-05-05T14:56:51Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #23)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8a9-3ef1-7a73-aaf9-c000868fbc26
author: oompah
created: 2026-05-05T15:02:15Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8a9-523d-753f-80b4-2c47d6c703dc
author: oompah
created: 2026-05-05T15:02:19Z

Retrying (attempt #23, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8a9-89d6-7b8d-b025-94ca8ba5539e
author: oompah
created: 2026-05-05T15:02:34Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #24)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8ae-94d5-7e34-88b1-05decf0190c4
author: oompah
created: 2026-05-05T15:08:04Z

Retrying (attempt #24, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8ae-98e8-7c8e-902f-e48dd55e0294
author: oompah
created: 2026-05-05T15:08:05Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8ae-db9b-7ef0-8caa-9d34c5e96eaf
author: oompah
created: 2026-05-05T15:08:22Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #25)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8b3-c083-7d4e-9c36-d6282adc602c
author: oompah
created: 2026-05-05T15:13:43Z

Retrying (attempt #25, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8b3-c4b1-76b6-9901-680885fac760
author: oompah
created: 2026-05-05T15:13:44Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8b4-138b-78ed-bb28-032e708c1103
author: oompah
created: 2026-05-05T15:14:04Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #26)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8b8-f761-77c0-994a-245d999d0bf0
author: oompah
created: 2026-05-05T15:19:25Z

Retrying (attempt #26, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8b8-fa05-7bb8-9b5d-c43b7cfaeaa1
author: oompah
created: 2026-05-05T15:19:25Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8b9-4ba4-7357-a0aa-f7b97cab05d2
author: oompah
created: 2026-05-05T15:19:46Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #27)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8bf-44e4-7d98-b902-bd5326a376ae
author: oompah
created: 2026-05-05T15:26:18Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8bf-4f1a-7bcb-afc9-c45214e1ba92
author: oompah
created: 2026-05-05T15:26:20Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8bf-a0bb-7812-a4d7-3b9c6756a03f
author: oompah
created: 2026-05-05T15:26:41Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8bf-fe71-7e96-a565-259eec3d6774
author: oompah
created: 2026-05-05T15:27:05Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c0-1774-7f36-bbfb-938dc360f582
author: oompah
created: 2026-05-05T15:27:12Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c0-3ec1-73bd-9059-8b1c1c2b377f
author: oompah
created: 2026-05-05T15:27:22Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c0-a857-70b7-8b04-eeae3d82da79
author: oompah
created: 2026-05-05T15:27:49Z

Retrying (attempt #2, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c0-abe9-7c31-9289-30fa4bb59488
author: oompah
created: 2026-05-05T15:27:50Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c0-ef1c-75c0-8881-5ba33e1ded1a
author: oompah
created: 2026-05-05T15:28:07Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 40s (attempt #3)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c1-9fdd-722a-baf7-400968c7795a
author: oompah
created: 2026-05-05T15:28:52Z

Retrying (attempt #3, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c1-a94f-7441-a593-9497d54fe72a
author: oompah
created: 2026-05-05T15:28:55Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c1-e92e-7a25-a732-268cf5d27c95
author: oompah
created: 2026-05-05T15:29:11Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 80s (attempt #4)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c3-62e0-7e92-aace-8de878f07226
author: oompah
created: 2026-05-05T15:30:48Z

Retrying (attempt #4, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c3-6b61-7de2-a5f5-3eff63e7d7a8
author: oompah
created: 2026-05-05T15:30:50Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c3-abca-71c5-a86b-de97e1cb8c85
author: oompah
created: 2026-05-05T15:31:06Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 160s (attempt #5)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c6-63d0-7109-bbc4-ebd619f1d0e9
author: oompah
created: 2026-05-05T15:34:04Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c6-6df5-78a6-bf23-9ec8b8dd64ea
author: oompah
created: 2026-05-05T15:34:07Z

Retrying (attempt #5, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8c6-ad3e-7a8f-9323-9d16cd8ee9ba
author: oompah
created: 2026-05-05T15:34:23Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #6)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8cb-7923-7728-8291-000640d57f03
author: oompah
created: 2026-05-05T15:39:38Z

Retrying (attempt #6, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8cb-8458-701b-bb9e-5e7ac89ecdf9
author: oompah
created: 2026-05-05T15:39:41Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8cb-c9c3-74f9-8557-c33ff446498f
author: oompah
created: 2026-05-05T15:39:58Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #7)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8d0-b0a4-748c-acf6-de07f3c225f2
author: oompah
created: 2026-05-05T15:45:20Z

Retrying (attempt #7, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8d0-b906-7cb5-9afb-90a5d2058fcd
author: oompah
created: 2026-05-05T15:45:22Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8d1-0b37-70cb-8b21-c6df48d452ba
author: oompah
created: 2026-05-05T15:45:43Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #8)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8d5-db59-7027-804e-f9209442534c
author: oompah
created: 2026-05-05T15:50:58Z

Retrying (attempt #8, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8d5-de44-7e48-bcd5-048d5b996e94
author: oompah
created: 2026-05-05T15:50:59Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8d6-24f4-74de-a413-9bf4a4661685
author: oompah
created: 2026-05-05T15:51:17Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #9)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8db-1fd4-7756-b052-8a8df4de929a
author: oompah
created: 2026-05-05T15:56:43Z

Retrying (attempt #9, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8db-2381-7124-b39c-8ab590d2af8d
author: oompah
created: 2026-05-05T15:56:44Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8db-6516-70ee-ba58-fcb915c6f8bb
author: oompah
created: 2026-05-05T15:57:01Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #10)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8e0-3def-70c7-927d-1e2d14cc89eb
author: oompah
created: 2026-05-05T16:02:19Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8e0-4555-7324-87ae-9a0990415ec4
author: oompah
created: 2026-05-05T16:02:21Z

Retrying (attempt #10, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8e0-8051-7d1b-9293-3a4fad325e71
author: oompah
created: 2026-05-05T16:02:36Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #11)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8e5-52c7-786c-a64e-f8fab683077b
author: oompah
created: 2026-05-05T16:07:52Z

Retrying (attempt #11, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8e5-5590-77b8-867d-9732e57acc68
author: oompah
created: 2026-05-05T16:07:52Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8e5-9704-797d-8f01-78306ff35aa9
author: oompah
created: 2026-05-05T16:08:09Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #12)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8e9-7c34-7a19-873e-80c7b8f5e322
author: oompah
created: 2026-05-05T16:12:25Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8e9-91b1-7080-b669-cbb994b693f3
author: oompah
created: 2026-05-05T16:12:30Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8e9-d9b2-7c6b-8dc6-f5eb573356ed
author: oompah
created: 2026-05-05T16:12:48Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8ea-5c14-7abe-8da9-8265f3f4d3fa
author: oompah
created: 2026-05-05T16:13:22Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8ea-60af-784d-9dd8-300b7812643d
author: oompah
created: 2026-05-05T16:13:23Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8ea-a4ef-78a6-aa23-e9aee5d7101f
author: oompah
created: 2026-05-05T16:13:40Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8eb-06a1-70ee-a1ca-61c3f2315d36
author: oompah
created: 2026-05-05T16:14:05Z

Retrying (attempt #2, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8eb-0984-7ed0-af9e-44b8886a9ca4
author: oompah
created: 2026-05-05T16:14:06Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8eb-4a63-7db3-911c-5a36f042f968
author: oompah
created: 2026-05-05T16:14:23Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 40s (attempt #3)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8eb-fabd-7874-afbf-c3b4d84d1fe4
author: oompah
created: 2026-05-05T16:15:08Z

Retrying (attempt #3, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8eb-fe60-74ba-bfea-089597c7041a
author: oompah
created: 2026-05-05T16:15:09Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8ec-3fb3-7d52-98b4-e05a8de21e6f
author: oompah
created: 2026-05-05T16:15:26Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 80s (attempt #4)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8ed-c434-72af-864f-ab97421b9018
author: oompah
created: 2026-05-05T16:17:05Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8ed-cd6e-7aec-8e3e-804faee15cc9
author: oompah
created: 2026-05-05T16:17:07Z

Retrying (attempt #4, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8ee-05fd-7f0b-a536-186e7816022e
author: oompah
created: 2026-05-05T16:17:22Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 160s (attempt #5)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8f0-bdf5-78c2-8dab-90cea861855f
author: oompah
created: 2026-05-05T16:20:20Z

Retrying (attempt #5, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8f0-c414-74ed-8a6e-841aaf956b24
author: oompah
created: 2026-05-05T16:20:22Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8f1-0de8-771c-a3f0-c04eca1b55c4
author: oompah
created: 2026-05-05T16:20:41Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #6)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8f5-f363-742e-8975-383fbe70353e
author: oompah
created: 2026-05-05T16:26:01Z

Retrying (attempt #6, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8f5-f6f8-7e5b-b209-fcbe1801642f
author: oompah
created: 2026-05-05T16:26:02Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8f6-445c-7478-a9e7-bae59f2b42ca
author: oompah
created: 2026-05-05T16:26:22Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #7)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8fb-27fe-74e9-b8f0-60f9daaebea3
author: oompah
created: 2026-05-05T16:31:43Z

Retrying (attempt #7, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8fb-2a3c-7897-bef2-2b43de7f2325
author: oompah
created: 2026-05-05T16:31:43Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df8fb-6cd0-7167-b7b3-4828655d4756
author: oompah
created: 2026-05-05T16:32:00Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #8)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df900-6316-7c48-99d4-2a9003ed92cd
author: oompah
created: 2026-05-05T16:37:25Z

Retrying (attempt #8, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df900-65b9-777d-86f3-8b3dca9425d9
author: oompah
created: 2026-05-05T16:37:26Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df900-ac4b-718e-a9e2-c01d3119fcf3
author: oompah
created: 2026-05-05T16:37:44Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #9)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df905-ad4e-7269-b479-d6e1ca0d3e5e
author: oompah
created: 2026-05-05T16:43:12Z

Retrying (attempt #9, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df905-b020-7a93-bf3f-d8dff9d5af3b
author: oompah
created: 2026-05-05T16:43:13Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df905-f0f2-7995-9e7c-6f7305f256cb
author: oompah
created: 2026-05-05T16:43:29Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #10)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df90a-bc0e-7065-9885-40f51517d6ca
author: oompah
created: 2026-05-05T16:48:44Z

Retrying (attempt #10, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df90a-bf46-7cd1-b829-543fb839b96d
author: oompah
created: 2026-05-05T16:48:44Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df90b-0031-7660-b74e-be8fe0646b3f
author: oompah
created: 2026-05-05T16:49:01Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 300s (attempt #11)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df90e-ec35-7445-8d16-74bc90bb4409
author: oompah
created: 2026-05-05T16:53:18Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df90e-faec-77df-bb72-e44b9ea9e6cd
author: oompah
created: 2026-05-05T16:53:22Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df912-f68c-70ee-b8af-1c59e709f226
author: oompah
created: 2026-05-05T16:57:43Z

Understanding: Implement adaptive polling in orchestrator.py. The polling loop (_fetch_all_reviews, _fetch_all_merged_branches) currently fetches ALL projects every tick regardless of webhook status. The fix: add is_webhook_healthy(project_id) helper that checks last_webhook_received_at is within ~150s, then skip polling for healthy projects. Stale/missing → poll. Plan: (1) add is_webhook_healthy method (2) filter _fetch_all_reviews to only stale projects (3) same for _fetch_all_merged_branches (4) unit tests. Webhook timestamps already tracked per-project (last_webhook_received_at field in Project model).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df91a-1b2b-7e9a-a61c-565e597c9b15
author: oompah
created: 2026-05-05T17:05:31Z

Discovery: The key polling code is in _fetch_all_reviews() (line ~1072) and _fetch_all_merged_branches() (line ~1105) in orchestrator.py. Both methods run all projects in parallel regardless of webhook health. The Project model already has last_webhook_received_at timestamp (added in oompah-zlz_2-yed). Root cause: no guard existed to skip forge API polling for projects with recent webhook delivery.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df91a-61cd-7bee-a12a-0edcc0977022
author: oompah
created: 2026-05-05T17:05:49Z

Implementation: Added is_webhook_healthy(project_id) helper (orchestrator.py:812) that checks if last_webhook_received_at is within 150 seconds. Projects healthy → skip forge API polling. Stale/missing → poll. Modified _fetch_all_reviews() and _fetch_all_merged_branches() to skip healthy projects. Falls back to 2-minute full_sync cadence for stale projects. Added 16 unit tests in tests/test_orchestrator_webhook_health.py. All 156 orchestrator tests pass.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df91a-d8d6-7305-9ffa-4416e44924d0
author: oompah
created: 2026-05-05T17:06:19Z

Agent completed successfully in 782s (5952619 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
