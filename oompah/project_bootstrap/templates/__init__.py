"""Canonical managed-project bootstrap templates bundled with oompah."""

from __future__ import annotations

from oompah.agent_instructions import render_oompah_task_agent_instructions

MARKER_NAME = "OOMPAH PROJECT BOOTSTRAP"
HTML_BEGIN_MARKER = f"<!-- BEGIN {MARKER_NAME} v:1 -->"
HTML_END_MARKER = f"<!-- END {MARKER_NAME} -->"
COMMENT_BEGIN_MARKER = f"# BEGIN {MARKER_NAME} v:1"
COMMENT_END_MARKER = f"# END {MARKER_NAME}"


AGENTS_MD = f"""\
# Agent Instructions

This project is managed by **oompah**. These instructions define the baseline
rules for agents working in this repository. Keep project-specific build,
test, and release details below this section.

{render_oompah_task_agent_instructions().strip()}

## Use Makefile Targets

Always use Makefile targets when one exists for the task you are performing.
Before running a raw command, check whether `make help` lists an equivalent
target. Makefile targets encode project-specific flags, setup, and sequencing.

## Documentation Rules

User-facing documentation lives in `docs/`. Design and implementation notes
live in `plans/`. If a doc tells someone what to do with the project, put it
in `docs/`. If it explains how the project works internally or how it might
work in the future, put it in `plans/`.

When creating diagrams in documentation, use Mermaid code blocks.

## Test Coverage Required

Code changes should include focused test coverage. Bug fixes should include a
test that reproduces the failure. Prefer the repository's existing test
patterns and run the relevant Makefile quality gate before handing off.

## Non-Interactive Shell Commands

Use non-interactive command flags in automation so commands do not hang on
prompts. Examples: `cp -f`, `mv -f`, `rm -f`, `rm -rf`, `ssh -o BatchMode=yes`,
and `scp -o BatchMode=yes`.
"""


MAKEFILE = f"""\
{COMMENT_BEGIN_MARKER}
# Project Makefile.
#
# Targets are documented inline with `## ` comments so `make help` stays
# current as this file is customized.
{COMMENT_END_MARKER}

.DEFAULT_GOAL := help

.PHONY: help init fmt fmt-check build test lint clean

help: ## Show this help.
\t@awk 'BEGIN {{FS = ":.*?## "; printf "Usage: make <target>\\n\\nTargets:\\n"}} \\
\t\t/^[a-zA-Z_-]+:.*?## / {{printf "  \\033[36m%-15s\\033[0m %s\\n", $$1, $$2}}' \\
\t\t$(MAKEFILE_LIST)

init: ## Initialize local repo prerequisites.
\t@set -e; \\
\tif [ ! -d .git ]; then \\
\t\techo "[init] git init"; \\
\t\tgit init; \\
\telse \\
\t\techo "[init] git: already initialized"; \\
\tfi; \\
\tif command -v oompah >/dev/null 2>&1; then \\
\t\techo "[init] oompah: $$(oompah --help >/dev/null 2>&1 && echo installed)"; \\
\telse \\
\t\techo "[init] oompah CLI not found. Install with:"; \\
\t\techo "       uv tool install git+https://github.com/lesserevil/oompah"; \\
\tfi

fmt: ## Format all source files in place.
\t@echo "fmt: not yet configured - edit Makefile" && exit 1

fmt-check: ## Check formatting without modifying files.
\t@echo "fmt-check: not yet configured - edit Makefile" && exit 1

build: ## Build the project.
\t@echo "build: not yet configured - edit Makefile" && exit 1

test: ## Run the test suite.
\t@echo "test: not yet configured - edit Makefile" && exit 1

lint: ## Run static analysis / linters.
\t@echo "lint: not yet configured - edit Makefile" && exit 1

clean: ## Remove build artifacts.
\t@echo "clean: not yet configured - edit Makefile" && exit 1
"""


DOCS_README = f"""\
{HTML_BEGIN_MARKER}
# Documentation

User-facing documentation for this project. Setup guides, troubleshooting,
operator how-tos, runbooks, and public API references belong here.

If you are trying to learn how to use, operate, administer, or troubleshoot
this project, you are in the right place. If you are trying to learn how it
works inside or how it might work in the future, see [`../plans/`](../plans/).

## Contents

Add project-specific documentation here as user-visible surfaces appear.

## Keeping Docs In Sync

Documentation is part of the user contract. Changes to commands,
configuration, runtime requirements, platform support, or other user-visible
behavior should update the relevant docs in the same change.
{HTML_END_MARKER}
"""


PLANS_README = f"""\
{HTML_BEGIN_MARKER}
# Plans

Design and implementation documentation for this project. Architecture notes,
proposed features, internal mechanism inventories, and design records belong
here.

If you are trying to learn how this project works inside or how it might work
in the future, you are in the right place. If you are trying to learn how to
use it, see [`../docs/`](../docs/).

## Plans Are Not Tasks

Creating or updating a design document here does not require a corresponding
oompah task. Plans can explore possible work before it is accepted or
scheduled. Create an oompah task when implementation begins or when the work
needs status, ownership, dependencies, or orchestration; the task can link to
the plan rather than duplicate it.

## Plan Docs Are Living Specifications

Every non-trivial plan should include acceptance criteria that define what
"done" means in testable terms.

```markdown
## Acceptance Criteria

- [ ] CRIT-1: <testable claim and verification path>
- [ ] CRIT-2: ...
```

Vague criteria such as "works well" or "is robust" do not count. Tie each item
to a passing test, command, or manual procedure with a clear pass/fail result.
These checklists describe the specification; they are not a substitute task
tracker.
{HTML_END_MARKER}
"""


GITIGNORE = f"""\
{COMMENT_BEGIN_MARKER}
# Language-agnostic baseline ignores for oompah-managed projects.
{COMMENT_END_MARKER}

# OS/editor noise
.DS_Store
Thumbs.db
.vscode/
.idea/
*.swp
*.swo
*~

# Secrets and local config
.env
.env.*
!.env.example
.netrc

# Common build artifacts
build/
dist/
out/
target/
node_modules/
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Logs
*.log
"""


PRE_COMMIT = f"""\
#!/usr/bin/env bash
{COMMENT_BEGIN_MARKER}
# Baseline pre-commit hook for oompah-managed projects.
#
# Install once per clone:
#   git config core.hooksPath scripts/githooks
{COMMENT_END_MARKER}

set -euo pipefail

fail() {{ echo "pre-commit: error: $*" >&2; exit 1; }}
warn() {{ echo "pre-commit: warning: $*" >&2; }}

if [[ -f Makefile ]] && grep -q '^fmt-check:' Makefile; then
    if ! make fmt-check >/dev/null 2>&1; then
        fail "formatter drift - run 'make fmt' and stage the changes"
    fi
fi

staged=$(git diff --cached --name-only)
if echo "$staged" | grep -q '^\\.oompah/tasks/'; then
    warn ".oompah/tasks changed in this commit; oompah should normally be the only writer"
fi

exit 0
"""


RELEASE_NOTES_WORKFLOW = f"""\
name: Filtered release notes

{COMMENT_BEGIN_MARKER}
# Publish release notes that omit commits changing only .oompah/**.
{COMMENT_END_MARKER}

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      tag:
        description: Release tag to refresh
        required: true
      previous_tag:
        description: Previous release tag
        required: true

permissions:
  contents: write

jobs:
  filter-notes:
    runs-on: ubuntu-latest
    env:
      GH_TOKEN: ${{{{ github.token }}}}
      TAG: ${{{{ inputs.tag || github.event.release.tag_name }}}}
      PREVIOUS_TAG: ${{{{ inputs.previous_tag || github.event.release.previous_tag_name }}}}
    steps:
      - name: Generate filtered commit notes
        shell: bash
        run: |
          set -euo pipefail
          if [[ -z "$PREVIOUS_TAG" ]]; then
            echo "Previous tag is required; rerun with workflow_dispatch and previous_tag." >&2
            exit 1
          fi
          generated=$(gh api --method POST "repos/$GITHUB_REPOSITORY/releases/generate-notes" \
            -f tag_name="$TAG" -f previous_tag_name="$PREVIOUS_TAG")
          body=$(jq -r .body <<<"$generated")
          commits=$(gh api "repos/$GITHUB_REPOSITORY/compare/$PREVIOUS_TAG...$TAG" --paginate \
            --jq '.commits[] | @base64')
          filtered=""
          while IFS= read -r encoded; do
            [[ -z "$encoded" ]] && continue
            commit=$(base64 --decode <<<"$encoded")
            sha=$(jq -r .sha <<<"$commit")
            subject=$(jq -r '.commit.message | split("\\n")[0]' <<<"$commit")
            files=$(gh api "repos/$GITHUB_REPOSITORY/commits/$sha" --jq '.files[].filename')
            [[ -z "$files" ]] && continue
            if grep -qv '^\\.oompah/' <<<"$files"; then
              filtered+="- $subject ($sha)"$'\\n'
            fi
          done <<<"$commits"
          {{
            echo "$body"
            echo
            echo "## Included commits"
            echo "$filtered"
          }} > RELEASE_NOTES.md
          gh release edit "$TAG" --notes-file RELEASE_NOTES.md
"""


CANONICAL_FILES: dict[str, str] = {
    "AGENTS.md": AGENTS_MD,
    "Makefile": MAKEFILE,
    ".gitignore": GITIGNORE,
    "docs/README.md": DOCS_README,
    "plans/README.md": PLANS_README,
    "scripts/githooks/pre-commit": PRE_COMMIT,
    ".github/workflows/filtered-release-notes.yml": RELEASE_NOTES_WORKFLOW,
}

EXECUTABLE_PATHS = {"scripts/githooks/pre-commit"}
