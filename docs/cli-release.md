# Releasing the oompah CLI

The oompah CLI release path is GitHub-only. Maintainers create a version tag,
then the `CLI Release` workflow builds wheel and source artifacts from that
tagged source state and attaches them to the matching GitHub Release.

The workflow does not publish to a package index and does not require package
index credentials.

## Create a release

1. Update `project.version` in `pyproject.toml`.
2. Run the quality gate:

   ```bash
   make test
   ```

3. Create and push a matching version tag:

   ```bash
   git tag -a v0.1.0 -m "oompah v0.1.0"
   git push origin v0.1.0
   ```

   The tag must match `project.version` with a leading `v`. For example,
   `project.version = "0.1.0"` must use tag `v0.1.0`.

4. Watch **Actions > CLI Release**. You can also run the workflow manually with
   an existing tag through **Run workflow** and the `tag` input.

The workflow checks out the tag, validates that the checkout is exactly that
tag, builds `dist/*.whl` and `dist/*.tar.gz`, smoke-installs the lightweight
CLI wheel, runs `oompah --help`, `oompah task --help`, and
`oompah project-bootstrap --help`, then creates or updates the GitHub Release
for that tag.

## Verify a release

Download the release artifacts from:

```text
https://github.com/lesserevil/oompah/releases/tag/v0.1.0
```

Install from the tag:

```bash
uv tool install "git+https://github.com/lesserevil/oompah@v0.1.0"
pipx install "git+https://github.com/lesserevil/oompah@v0.1.0"
```

Install from the wheel artifact:

```bash
uv tool install "https://github.com/lesserevil/oompah/releases/download/v0.1.0/oompah-0.1.0-py3-none-any.whl"
pipx install "https://github.com/lesserevil/oompah/releases/download/v0.1.0/oompah-0.1.0-py3-none-any.whl"
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
