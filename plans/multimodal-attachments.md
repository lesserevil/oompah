# Plan: Multimodal Attachments (Git-LFS Backed)

Add first-class image/audio attachment support across the oompah pipeline:
issues carry a list of attachment paths, those attachments are stored in
the project repo via git LFS, the orchestrator passes them to multimodal
models, and any images the model produces are stored back into the same
attachment store and linked on the issue. The dashboard surfaces all of
this.

This is the "big version" referenced in `plans/multimodal-attachments.md`'s
predecessor discussion. The smaller version (paths-by-convention in the
description, no UI, no return path) is rejected here in favor of one
coherent design.

---

## Goals

- A user can drop a screenshot, mockup, PDF page, or audio clip onto a
  tracker task (via dashboard or CLI) and have an agent reason over it.
- An agent can produce images (diagrams, annotated screenshots, generated
  UI mocks) and attach them back to the issue as part of its work.
- Attachments live in the project's git repository under git LFS so they
  travel with the code, are reviewable in PRs, and don't bloat the regular
  git history.
- The dashboard renders attachments inline (thumbnails, audio players, PDF
  previews where possible) on issue detail and on the kanban card.
- Per-focus model overrides (`plans/per-focus-models.md`) cooperate with
  modality capability — non-multimodal models silently get a text-only
  prompt with attachment paths listed; multimodal models get the real
  bytes.

## Non-goals

- **No external blob store.** We commit to git LFS. If users want S3 or
  similar later, the storage layer is small enough to swap.
- **No new transcoding pipeline.** PDFs go to the model as PDFs (or as
  rendered page images, see "Open questions"); audio goes as the original
  format. We don't re-encode.
- **No general-purpose file uploads.** Only image / audio / PDF. Other
  files (binaries, archives) are rejected at upload time.
- **No model-to-model image passing across turns** beyond what the
  underlying chat completion already supports — we don't re-fetch and
  re-attach an image we just generated unless the agent explicitly
  references it.

---

## Architecture

### Storage layer: git LFS under `.oompah/attachments/`

Each project repo gets a directory:

```
.oompah/attachments/
├── <issue-identifier>/
│   ├── <hash>-<original-name>.png
│   ├── <hash>-<original-name>.wav
│   └── outputs/
│       └── <turn>-<hash>-<filename>.png
└── .gitattributes
```

- One subdirectory per issue identifier (e.g. `oompah-9k1/`).
- Files are named `<sha256-prefix>-<original-name>` to avoid collisions
  while preserving a human-readable name.
- Agent-produced outputs go in `outputs/` to keep input vs output
  attribution explicit.
- A `.gitattributes` in `.oompah/attachments/` declares LFS for common
  binary extensions:
  ```
  *.png filter=lfs diff=lfs merge=lfs -text
  *.jpg filter=lfs diff=lfs merge=lfs -text
  *.jpeg filter=lfs diff=lfs merge=lfs -text
  *.gif filter=lfs diff=lfs merge=lfs -text
  *.webp filter=lfs diff=lfs merge=lfs -text
  *.pdf filter=lfs diff=lfs merge=lfs -text
  *.mp3 filter=lfs diff=lfs merge=lfs -text
  *.wav filter=lfs diff=lfs merge=lfs -text
  *.m4a filter=lfs diff=lfs merge=lfs -text
  *.mp4 filter=lfs diff=lfs merge=lfs -text
  ```

The store is a thin Python class (`oompah/attachments.py`):

```python
class AttachmentStore:
    def __init__(self, project_root: str): ...
    def add(self, issue_identifier: str, src_path: str, *,
            generated: bool = False) -> str:
        """Copy src into the store, return the canonical relative path
        (e.g. '.oompah/attachments/foo-1/abc123-screenshot.png')."""
    def list(self, issue_identifier: str) -> list[Attachment]: ...
    def open(self, rel_path: str) -> bytes: ...
    def absolute(self, rel_path: str) -> str: ...
    def ensure_lfs_configured(self) -> None: ...
    def commit(self, paths: list[str], message: str) -> None: ...
```

The `Attachment` record carries `path`, `mime_type`, `size`, `created_at`,
`generated` (bool), and `turn` (int | None) for outputs.

### Project setup

When a project is registered, oompah runs (idempotently):

```
git lfs install --local
mkdir -p .oompah/attachments
# write .gitattributes if missing
git add .oompah/attachments/.gitattributes
```

If `git lfs` is not installed, registration succeeds with a warning and the
attachment features are disabled for that project. Surface this via a
`lfs_available: bool` on `Project`.

### Issue model: `attachments: list[str]`

`oompah/models.py:Issue` gains:

```python
attachments: list[str] = field(default_factory=list)
```

Values are repo-relative paths (e.g.
`.oompah/attachments/oompah-9k1/abc123-mock.png`). The list is canonical:
the dashboard, the prompt renderer, and the agent all read from it.

### Tracker persistence

Attachment records are tracker-owned metadata. Beads is the existing backend;
Backlog.md is the next supported backend. Beans is not planned.

Beads has no first-class attachment field. Three options surveyed:

1. **`metadata` JSON** (`bd create --metadata @file.json` /
   `bd update --metadata`). Programmatic, structured, hidden from casual
   readers — but writable from `bd`.
2. **A trailing block in the description** (e.g. `<!-- attachments:\n
   ['.oompah/attachments/...'] -->`). Visible in `bd show` but ugly and
   re-edited by humans/agents.
3. **A sidecar file** at `.oompah/attachments/<id>/manifest.json`.
   Decoupled from beads but adds a second source of truth.

**Choice for beads: option 1, `metadata`**, with the sidecar manifest as a
fallback cache for performance (the orchestrator reads many issues per tick;
parsing JSON metadata from `bd list --json` is cheap, but having a manifest
lets the dashboard render thumbnails without a `bd` call).

The metadata key is `oompah.attachments` and holds a list of objects:

```json
{
  "oompah.attachments": [
    {
      "path": ".oompah/attachments/oompah-9k1/abc-mock.png",
      "mime": "image/png",
      "size": 18324,
      "generated": false,
      "added_by": "user",
      "added_at": "2026-04-28T12:00:00Z"
    }
  ]
}
```

For Backlog.md, persist the same `oompah.attachments` records through the
Backlog.md adapter's structured task metadata/front matter when available. If
Backlog.md cannot store structured metadata directly, use a documented oompah
sidecar under `.oompah/attachments/<id>/manifest.json`; do not append ad hoc
attachment prose to the task body.

The tracker layer (`oompah/tracker.py:_parse_issue`) reads
`metadata["oompah.attachments"]` into `Issue.attachments` as
`list[str]` (just the paths — full records stay in the metadata for the
dashboard to fetch on demand). Writes go through a new
`tracker.set_attachments(identifier, list[Attachment])`.

### Prompt rendering

`oompah/prompt.py:render_prompt` currently returns `str`. It needs to
return one of:

- a plain `str` (text-only providers / no attachments), or
- an OpenAI-style content array
  `list[dict[str, Any]]` where each entry is
  `{type: "text", text: ...}`, `{type: "image_url", image_url: {...}}`, or
  `{type: "input_audio", input_audio: {...}}`.

Introduce a small return type:

```python
@dataclass
class RenderedPrompt:
    text: str                                 # canonical text rendering
    parts: list[dict[str, Any]] | None = None # multimodal content array
```

When `parts` is `None`, callers send `{role: "user", content: text}`. When
`parts` is set, callers send `{role: "user", content: parts}`.

### Provider modality capability

`ModelProvider` gains an optional per-model capability map:

```python
model_capabilities: dict[str, list[str]] = field(default_factory=dict)
# e.g. {"nemotron-3-nano-omni": ["text", "image", "audio"],
#       "gpt-4o-mini": ["text", "image"]}
```

A new `_resolve_capabilities(provider, model)` returns the capability set
for the resolved model (defaulting to `["text"]` when not declared). The
orchestrator passes this into the renderer:

- If the model supports `image`, attachments with `image/*` mime go in as
  `image_url` parts (data URLs from LFS pulls; remote URL when the
  provider supports it).
- If the model supports `audio`, audio attachments go in as `input_audio`
  parts.
- Unsupported attachments are still listed in the text portion as paths
  with a one-line note ("(image not sent — model lacks vision)") so the
  agent at least knows they exist.

### Inbound: sending attachments

Where this plugs in (`oompah/orchestrator.py:_run_api_worker`, after the
focus selection that we just added):

1. Resolve focus, profile, provider, model — already done.
2. Resolve `caps = _resolve_capabilities(provider, model)`.
3. After workspace creation, materialize attachments with
   `git lfs pull --include=...` (or rely on the worktree already having
   LFS smudged).
4. Read each attachment from disk, base64-encode, and build the parts
   array. For very large attachments, hard-cap at e.g. 20 MB total per
   prompt and elide the rest with a warning comment.
5. Pass `RenderedPrompt(text, parts)` into `ApiAgentSession.run_task`.

`api_agent.py` needs a small change: accept either `prompt: str` *or*
`prompt: RenderedPrompt`, and build the first user message accordingly.
Subsequent turns (tool results) remain text.

### Outbound: agent produces images

Add a tool the agent can call, exposed only when the resolved model has
the `image` capability and the focus is in an output-allowed list (initial
allowlist: `frontend`, `docs`, plus any focus that explicitly opts in via
a new `allow_image_output: bool = False` flag on `Focus`):

```
attach_image(filename: str, content_base64: str, caption: str | None) -> str
```

Implementation in `api_agent.py`:

- Decode bytes, write into the workspace at
  `.oompah/attachments/<issue>/outputs/<turn>-<hash>-<filename>`.
- Stage the file (`git add`) and commit at the end of the agent run as
  part of the existing commit step.
- Return the canonical relative path.

After the agent run, the orchestrator scans `outputs/` for new files (or
trusts what `attach_image` returned), commits them, and updates the
tracker task's `oompah.attachments` metadata with `generated: true`
entries. The completion comment lists generated artifacts so reviewers
see them.

### Dashboard UI

#### Issue card (kanban)

- A small thumbnail strip in the bottom-right of cards with attachments
  (max 3 thumbs, "+N more" if longer).
- A paperclip icon with count when no thumbnails are renderable.

#### Issue detail

- New "Attachments" section, two columns: Inputs / Outputs.
- Inline rendering: `<img>` for images, `<audio controls>` for audio,
  `<embed>` or PDF.js fallback for PDFs.
- Drag-and-drop upload zone that posts to a new endpoint:
  ```
  POST /api/v1/issues/{identifier}/attachments
  multipart/form-data: file=<binary>
  ```
  Server pipes the file through `AttachmentStore.add`, updates tracker
  metadata, commits the change. Response: the new `Attachment` record.
- Delete button per attachment (only for user-added ones; generated ones
  require explicit "remove generated"). Deletes are commits, not file
  rewrites — we keep history.

#### Server endpoints

```
GET    /api/v1/issues/{identifier}/attachments          # list
POST   /api/v1/issues/{identifier}/attachments          # upload
GET    /api/v1/attachments/{path}                       # binary stream
DELETE /api/v1/attachments/{path}                       # remove from issue
```

`GET /api/v1/attachments/{path}` validates the path is under the project's
`.oompah/attachments/` directory before serving — anything else returns
404. Important: this is the only place we serve LFS-backed bytes, so the
path-validation check is security-critical.

### Validation and limits

- Whitelist mime types: `image/png`, `image/jpeg`, `image/webp`,
  `image/gif`, `image/svg+xml`, `application/pdf`, `audio/wav`,
  `audio/mpeg`, `audio/mp4`. Reject others.
- Per-attachment cap: 25 MB. Per-issue cap: 200 MB. Enforced at upload
  and at agent-output time (over-cap output attachments are dropped with
  a warning comment on the issue).
- SVGs are sanitized (scripts stripped) before being served back to the
  dashboard.

### Concurrency and worktrees

Worktrees share the LFS object cache with the main repo. Each worker
already operates in its own worktree (`oompah/workspace.py`), so
`git lfs pull --include=.oompah/attachments/<id>/` runs in the worktree
and only fetches what that issue needs. Output commits go on the issue
branch as part of the normal agent commit, then merge into main when the
PR is merged — no special handling needed.

---

## Files to touch

| Area | File | Change |
|---|---|---|
| Store | `oompah/attachments.py` (new) | `AttachmentStore`, `Attachment` dataclass, LFS bootstrap |
| Issue model | `oompah/models.py` | Add `attachments: list[str]` to `Issue` |
| Tracker | `oompah/tracker.py` | Parse backend metadata for `oompah.attachments`; add `set_attachments()` |
| Provider model | `oompah/models.py` | Add `model_capabilities` to `ModelProvider`, `to_dict`/`from_dict` |
| Renderer | `oompah/prompt.py` | Return `RenderedPrompt`; build content parts |
| API agent | `oompah/api_agent.py` | Accept `RenderedPrompt`; new `attach_image` tool |
| Orchestrator | `oompah/orchestrator.py` | Resolve capabilities; pass attachments into render; commit generated outputs; update tracker metadata |
| Focus | `oompah/focus.py` | `allow_image_output: bool = False` field |
| Project setup | `oompah/projects.py` | LFS bootstrap on register; `lfs_available` flag |
| Server | `oompah/server.py` | 4 attachment endpoints; serve under `/api/v1/attachments/{path}` with path validation |
| Templates | `oompah/templates/dashboard.html` | Thumbnails on cards; attachments section in detail; upload zone |
| Templates | `oompah/templates/foci.html` | Toggle for `allow_image_output` |
| Tests | `tests/test_attachments.py` (new) | Store CRUD, LFS detection, mime whitelist, size limits |
| Tests | `tests/test_orchestrator_handlers.py` | Capability resolution; multimodal vs text fallback |
| Tests | `tests/test_server_attachments.py` (new) | Path traversal protection; upload + serve roundtrip |
| Docs | `README.md`, `WORKFLOW.md` | Brief mention; link to this plan |

## Test plan

1. **Store roundtrip:** add → list → open → delete; canonical path is
   stable across runs.
2. **LFS bootstrap idempotent:** register a project twice, only one
   `.gitattributes` write, no duplicate filters.
3. **LFS not installed:** project registers with a warning; upload
   endpoint returns 503 with a clear message.
4. **Issue model roundtrip:** tracker metadata read+write of
   `oompah.attachments` parses into `Issue.attachments` for beads and
   Backlog.md.
5. **Renderer:** text-only provider gets a string; multimodal provider
   gets a content array with the right mime types.
6. **Capability fallback:** a focus pinned to a text-only model still
   dispatches; attachment paths appear in the text body with the "not
   sent" note.
7. **Tool: `attach_image`:** writes under `outputs/`, gets staged,
   appears in the post-run commit.
8. **Server path validation:** `GET /api/v1/attachments/../../etc/passwd`
   returns 404, not the file.
9. **Per-issue size cap:** 11th attachment over the limit is rejected at
   upload; 11th generated attachment is dropped with a warning comment
   on the issue.
10. **Mime whitelist:** uploading a `.exe` is rejected with 415.
11. **SVG sanitization:** `<script>` inside an uploaded SVG is stripped
    before the file is served.

## Rollout

1. Land `AttachmentStore` + LFS bootstrap behind a feature flag
   (`OOMPAH_ATTACHMENTS=1`). No model wiring yet.
2. Wire inbound (model receives attachments) + capability resolution.
   Test with one focus (`frontend`) pinned to a multimodal model.
3. Wire outbound (`attach_image` tool) + auto-commit + metadata writeback.
4. Dashboard rendering and upload UI.
5. Drop the feature flag once all four phases are stable in dogfood.

Each phase is its own PR. Phase 1 is small and self-contained (store +
LFS + tests). Phase 2 carries the modality work and is the largest.

## Open questions

1. **PDF strategy.** Some providers accept PDFs natively; most don't.
   Should we render PDFs to per-page PNGs at attach time (extra
   dependency: `pdf2image` / `pdfium`) so every multimodal model sees
   them, or punt and only send PDFs to providers that accept them? Lean
   toward render-on-attach.
2. **Audio length cap.** A 10-minute WAV is huge as base64. Should we
   chunk + summarize or refuse > N seconds? Probably refuse > 60s
   initially; revisit if used.
3. **Generated-image attribution.** When the agent generates an image,
   should it always commit, or should it ask first? Default to commit
   inside the issue branch (cheap to undo via `git revert`); a
   per-project "approve generated outputs before commit" setting can
   come later if review burden becomes real.
4. **External image URLs.** If a user pastes an external image URL in
   the issue description, should oompah download and store it? Probably
   not — surfacing a "convert to attachment" button in the dashboard is
   safer and explicit.
5. **Cross-issue references.** Do we want to allow one issue's
   attachments to be referenced by another (shared mock)? If yes, paths
   are already global within the repo; we just need a UI affordance.
   Defer until requested.
6. **Tracker upstreams.** Whether to push for first-class attachment
   support upstream in beads or Backlog.md, or stay in backend metadata
   indefinitely. The metadata approach works today for beads; Backlog.md
   should follow the tracker-backends plan before inventing another
   storage shape.
