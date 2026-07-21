# GitLab Forge Parity Plan

## Summary

Add GitLab.com and GitLab 17.0+ self-managed support as a first-class forge
alongside GitHub. A project will explicitly declare its forge and GitLab base
URL, use GitLab Issues, Merge Requests, pipelines, and webhooks end-to-end,
and retain Oompah's existing native Markdown tracker, dashboard, release
delivery, YOLO, and state-branch behavior. GitLab merge trains are out of
scope for v1; ordinary GitLab auto-merge uses merge-when-pipeline-succeeds.

## Core architecture and interfaces

- Replace GitHub-derived forge detection with explicit project fields:
  - `forge_kind`: `github` or `gitlab`, inferred for existing GitHub projects
    during deserialization.
  - `forge_base_url`: canonical web/API origin; default `https://github.com`
    or `https://gitlab.com`, required for self-managed GitLab.
  - Keep `access_token` project-scoped; preserve existing GitHub environment
    and CLI fallbacks, and add GitLab `GITLAB_TOKEN` / `glab` fallback per
    configured hostname.
- Generalize GitHub-named project settings and APIs:
  - `github_issue_intake_enabled` becomes forge-neutral
    `external_issue_intake_enabled`, with old persisted/API input accepted as
    a backward-compatible alias.
  - `tracker_owner` / `tracker_repo` become provider-neutral
    namespace/project fields in behavior while preserving their serialized
    names for compatibility.
  - Add `gitlab_issues` tracker kind; retain `github_issues` and `oompah_md`.
  - Do not add GitLab Issue Board support; Oompah's dashboard remains
    authoritative.
- Formalize provider contracts rather than provider-specific conditionals:
  - Expand `SCMProvider` with normalized review state, changed files/commits,
    branch-head lookup, commit/pipeline CI status, review comments, labels,
    review creation/rebase/merge/close, and ordinary auto-merge capability.
  - Define normalized CI states: `passed`, `failed`, `pending`, `unknown`,
    plus structured warnings/capability failures.
  - Ensure all release-delivery, review, YOLO, churn, backport, and task-close
    logic consumes only this contract.

## GitLab implementation

- Complete and harden `GitLabProvider`:
  - Respect configured self-managed API base URLs, URL-encode nested project
    paths, paginate every list endpoint, and apply the same timeout, retry,
    rate-limit, and error-redaction behavior as GitHub.
  - Normalize MR fields including approvals/reviewers, draft/WIP, conflicts,
    divergence, mergeability, labels, source/target branches, commit list,
    changed paths, and pipeline state.
  - Implement CI lookup from commit/MR pipelines and jobs; surface failed or
    pending pipeline details in Reviews, Release Delivery, YOLO, and
    remediation tasks.
  - Preserve history by default: do not force squash merges. Honor repository
    merge policy and only request squash when an explicit future project policy
    enables it.
  - Implement ordinary GitLab auto-merge with
    `merge_when_pipeline_succeeds`; if GitLab rejects it because approvals or
    policy are unmet, retain the MR and surface the actionable reason. Do not
    use or emulate merge trains in v1.
- Add `GitLabIssueTracker`, modeled on the existing tracker protocol:
  - Use GitLab Issues, notes, labels, milestones/metadata where applicable,
    and issue links for parent/dependency relationships.
  - Preserve Oompah canonical statuses through `oompah:status:*` labels;
    enforce authorized actors, revert unauthorized status-label changes, and
    keep comments/audit behavior equivalent to GitHub.
  - Support full task lifecycle, epics/children, dependencies, attachments
    metadata, labels, comments, status transitions, archival, and native-task
    import/export behavior.
- Replace the GitHub-only intake bridge with a forge-neutral external-intake
  bridge:
  - Import GitLab issue bodies/comments into native Markdown tasks with
    provenance fields such as `oompah.external.gitlab`.
  - Mirror terminal native-task outcomes back to the originating GitLab issue
    by comment and closure.
  - Treat all GitLab-originated text, webhook payloads, MR descriptions, issue
    comments, and CI logs as untrusted under the existing prompt-injection
    contract.

## Webhooks, UI, bootstrap, and operations

- Keep GitHub's `gh webhook forward` path unchanged. Add a separate GitLab hook
  manager:
  - Require `OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL`, a public HTTPS base URL for the
    Oompah server.
  - Create, reconcile, rotate, and validate project hooks through GitLab's
    Project Hooks API using each project's secret.
  - Subscribe to push, merge request, issue, note/comment, pipeline, job, and
    label-relevant events; normalize them into the existing event bus.
  - Maintain polling as a backup and expose per-project hook health, delivery
    timestamps, authentication failures, and remediation instructions in the
    dashboard.
- Extend project creation/edit/detail APIs, ACP tools, and Projects UI:
  - Forge selector, GitLab base URL, GitLab tracker/intake controls, token
    masking, webhook endpoint/health, and GitLab-specific permission guidance.
  - Display “Merge Request” terminology and GitLab URLs where appropriate
    without changing shared dashboard/release-delivery workflows.
- Make bootstrap forge-aware:
  - Create/validate GitLab labels, verify GitLab token scopes (`api` or
    equivalent minimum project permissions), validate public webhook
    reachability, and report CI/pipeline-read capability.
  - Update operator docs, project-bootstrap templates, issue-intake docs,
    webhook docs, token-permission docs, troubleshooting, and
    prompt-injection inventory.
  - Leave Oompah's GitHub Release-based CLI distribution unchanged; GitLab
    support applies to managed projects, not Oompah's release hosting.

## Migration, testing, and acceptance

- Migration:
  - Existing projects deserialize as GitHub projects with unchanged behavior
    and no required configuration edits.
  - Add validation that rejects ambiguous or mismatched forge URL/tracker
    combinations before saving a project.
  - Provide a dry-run project-bootstrap check for GitLab credentials, hook
    creation, labels, issue-tracker access, MR API access, pipeline visibility,
    and state-branch push access.
- Tests:
  - Run the same provider-contract suite against GitHub and GitLab HTTP
    fixtures: pagination, auth failures, self-managed URL handling, nested
    groups, MR lifecycle, labels, history-preserving merge, auto-merge
    rejection, CI states, changed files, and commits.
  - Add GitLab issue-tracker lifecycle tests for every `TrackerProtocol`
    operation, status-label authorization, parent/dependency links, comments,
    external intake, terminal mirroring, and untrusted-content boundaries.
  - Add webhook tests for signature/token validation, all subscribed GitLab
    events, deduplication, project matching, hook-health degradation, and
    polling fallback.
  - Add end-to-end GitLab project fixtures covering task dispatch → branch →
    MR → pipeline → merge → state update, plus selected release delivery → MR
    → target-branch pipeline monitoring/remediation.
  - Maintain a gated integration suite against GitLab.com and a GitLab 17.x
    self-managed fixture; standard unit tests remain network-free.
- Acceptance criteria:
  - An operator can create and bootstrap GitLab.com or self-managed GitLab
    projects entirely from Oompah's UI/API.
  - GitLab-backed and native-with-GitLab-intake projects support the same task,
    epic, review, release-delivery, CI, webhook, and YOLO workflows as GitHub
    projects.
  - GitHub behavior and persisted project records remain backward-compatible.
  - GitLab merge trains are visibly unsupported rather than silently treated
    as ordinary auto-merge.
  - Full project test target and both forge contract suites pass.

## Assumptions

- GitLab.com and GitLab 17.0+ are supported.
- GitLab Issue Boards are not integrated.
- Operators provide a stable public HTTPS endpoint for GitLab webhook delivery.
- GitLab v1 supports ordinary auto-merge only, not merge trains.
