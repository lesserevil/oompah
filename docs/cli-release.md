# Releasing the oompah CLI

The oompah CLI release path is GitHub-only. Maintainers create a version tag,
then the `CLI Release` workflow builds wheel and source artifacts from that
tagged source state and attaches them to the matching GitHub Release.

The workflow does not publish to a package index and does not require package
index credentials.

## 1.0 release train

The 1.0 release uses a stable release branch with distinct draft and final tags:

- Release branch: `release/1.0`
- Draft release tag: `v1.0.0-draft` (force-movable during RC iteration)
- Final release tag: `v1.0.0` (immutable)
- Package version: `1.0.0`

Maintainers may force-move `v1.0.0-draft` while iterating on release
candidates. The final `v1.0.0` tag must never be force-moved.

## Cut the release branch

Run this checklist before creating the first `v1.0.0-draft` release.

1. Confirm `main` is clean and current:

   ```bash
   git fetch origin --prune
   git switch main
   git pull --ff-only origin main
   git status --short
   git log --oneline HEAD..origin/main
   git log --oneline origin/main..HEAD
   ```

   `git status --short` and both `git log` commands must produce no output.

2. Cut and push `release/1.0` from that clean `main`:

   ```bash
   git switch -c release/1.0 main
   git push -u origin release/1.0
   ```

3. Confirm the release branch package metadata is set to
   `project.version = "1.0.0"` in `pyproject.toml`. If it is not, update
   `pyproject.toml`, refresh `uv.lock`, commit the change on `release/1.0`, and
   push the branch:

   ```bash
   uv lock
   git add pyproject.toml uv.lock
   git commit -m "Set package version to 1.0.0"
   git push origin release/1.0
   ```

4. Run the quality gates on `release/1.0`:

   ```bash
   make test
   make check-secrets
   git status --short
   ```

   Do not create or move `v1.0.0-draft` unless the quality gates pass and the
   release branch is clean.

## Create a draft release

1. Check out the `release/1.0` branch and ensure `project.version = "1.0.0"` in
   `pyproject.toml`.

2. Run the quality gate:

   ```bash
   make test
   ```

3. Create or force-move the draft tag and push:

   ```bash
   git tag -f v1.0.0-draft -m "oompah v1.0.0-draft"
   git push -f origin v1.0.0-draft
   ```

4. Watch **Actions > CLI Release**. The workflow creates or updates the GitHub
   Release for `v1.0.0-draft`.

5. Verify the draft artifacts from:

   ```text
   https://github.com/lesserevil/oompah/releases/tag/v1.0.0-draft
   ```

   The draft release must include `oompah-1.0.0-py3-none-any.whl`,
   `oompah-1.0.0.tar.gz`, generated notes for `v1.0.0-draft`, and GitHub tag
   and wheel install commands. Install from both the draft tag and the wheel
   artifact in a clean tool environment:

   ```bash
   uv tool install --force "git+https://github.com/lesserevil/oompah@v1.0.0-draft"
   oompah --help
   oompah task --help

   uv tool install --force "https://github.com/lesserevil/oompah/releases/download/v1.0.0-draft/oompah-1.0.0-py3-none-any.whl"
   oompah --help
   oompah task --help
   ```

Only `v1.0.0-draft` may be force-moved. Do not create `v1.0.0` until draft
verification passes, and never delete, force-push, or retarget `v1.0.0` after
it is pushed.

## Create a final release

1. Ensure all draft findings are resolved on `release/1.0` and merged back to
   `main`.

2. Run the quality gate:

   ```bash
   make test
   ```

3. Create the immutable final tag and push:

   ```bash
   git tag -a v1.0.0 -m "oompah v1.0.0"
   git push origin v1.0.0
   ```

   The tag must match `project.version` with a leading `v`. For example,
   `project.version = "1.0.0"` must use tag `v1.0.0`.

4. Watch **Actions > CLI Release**. You can also run the workflow manually with
   an existing tag through **Run workflow** and the `tag` input.

The workflow checks out the tag, validates that the checkout is exactly that
tag, builds `dist/*.whl` and `dist/*.tar.gz`, smoke-installs the lightweight
CLI wheel, runs `oompah --help` and `oompah task --help`, then creates or
updates the GitHub Release for that tag.

## Verify a release

Download the release artifacts from:

```text
https://github.com/lesserevil/oompah/releases/tag/v1.0.0
```

Install from the tag:

```bash
uv tool install "git+https://github.com/lesserevil/oompah@v1.0.0"
pipx install "git+https://github.com/lesserevil/oompah@v1.0.0"
```

Install from the wheel artifact:

```bash
uv tool install "https://github.com/lesserevil/oompah/releases/download/v1.0.0/oompah-1.0.0-py3-none-any.whl"
pipx install "https://github.com/lesserevil/oompah/releases/download/v1.0.0/oompah-1.0.0-py3-none-any.whl"
```

Verify the installed console script:

```bash
oompah --help
oompah task --help
```

The default release artifact is for managed-project contributors and agents. It
installs the standalone `oompah task` client and does not install or configure
the oompah service runtime. Service operators should install the server extra
from a cloned repository with `uv pip install -e '.[server]'` or use
`make setup`.

## Release notes

The workflow generates release notes with the exact tag and wheel artifact name
from the built `dist/` directory. The generated notes include the `uv tool` and
`pipx` install commands for both the Git tag and the wheel artifact URL.
