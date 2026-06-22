# Releasing the oompah CLI

The oompah CLI release path is GitHub-only. Maintainers create a version tag,
then the `CLI Release` workflow builds wheel and source artifacts from that
tagged source state and attaches them to the matching GitHub Release.

The workflow does not publish to a package index and does not require package
index credentials.

## 1.0 Release Train

The 1.0 release uses a stable branch, a movable draft tag, and an immutable
final tag:

| Artifact | Value |
|---|---|
| Release branch | `release/1.0` |
| Draft release tag | `v1.0.0-draft` |
| Final release tag | `v1.0.0` |
| Package version | `1.0.0` |

**Draft tags** (`v1.0.0-draft`) are intentionally force-movable. Maintainers
may retag and rerun the workflow while iterating on release candidates. The
workflow marks draft-tag releases as a GitHub prerelease.

**Final tags** (`v1.0.0`) are immutable once published. Do not force-move a
final release tag.

## Create a release

### Draft release

1. Update `project.version` in `pyproject.toml` to `1.0.0`.
2. Run the quality gate:

   ```bash
   make test
   ```

3. Create and push the draft tag (force-movable; rerun as needed):

   ```bash
   git tag -f v1.0.0-draft -m "oompah v1.0.0-draft"
   git push -f origin v1.0.0-draft
   ```

4. Watch **Actions > CLI Release**. The workflow creates or updates a GitHub
   prerelease for `v1.0.0-draft`.

### Final release

Once draft verification passes, create the immutable final tag:

1. Create and push the final tag (do **not** force-move this):

   ```bash
   git tag -a v1.0.0 -m "oompah v1.0.0"
   git push origin v1.0.0
   ```

   The tag must match `project.version` with a leading `v`. For example,
   `project.version = "1.0.0"` must use tag `v1.0.0`.

2. Watch **Actions > CLI Release**. You can also run the workflow manually with
   an existing tag through **Run workflow** and the `tag` input.

The workflow checks out the tag, validates that the checkout is exactly that
tag, builds `dist/*.whl` and `dist/*.tar.gz`, smoke-installs the lightweight
CLI wheel, runs `oompah --help`, `oompah task --help`, and
`oompah project-bootstrap --help`, then creates or updates the GitHub Release
for that tag.

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
oompah project-bootstrap --help
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

The generated notes also include an **Upgrading from an earlier install**
section. This section is important whenever a release adds new CLI subcommands
or modules that were absent in older installed binaries — operators who upgrade
in-place via `uv tool upgrade oompah` will pick up the new code automatically,
but operators with stale installs need to be told explicitly.

Notable upgrade requirement: the `project-bootstrap` subcommand (`oompah
project-bootstrap status/preview/apply`) was added after 1.0. Any operator
who installed oompah before that feature shipped must reinstall to get the
`project_bootstrap` module:

```bash
uv tool upgrade oompah
# or
uv tool install --reinstall git+https://github.com/lesserevil/oompah
```
