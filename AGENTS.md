# Agent instructions

Maintenance instructions extracted from the [README](README.md). See
[CONTRIBUTING.md](CONTRIBUTING.md) for package change requirements and additional
validation checks.

## Package updates

Use the official release feeds configured in each package's `.upstream.json`.
Recipes, dependencies, and launchers are maintained here; preserve existing
upstream attribution and license notices. Do not import third-party packaging
changes or automatically downgrade packages.

Run an update locally without creating a PR:

```bash
python scripts/update.py orca
```

Or open a PR from a **clean checkout of the latest `master`** using the existing
GitHub CLI login:

```bash
python scripts/update.py orca --pr --repo filippov-au/arch-packages
```

PR mode switches the checkout to its update branch. Use a separate checkout for
each package when checking multiple packages.

Review the recipe, source URLs, checksums, dependency changes, and build results
before merging. Bot-created PR checks can require approval: a maintainer with
write access must select **Approve workflows to run** in the PR before the checks
execute. This is expected
[GitHub token behavior](https://docs.github.com/en/actions/concepts/security/github_token#when-github_token-triggers-workflow-runs).
Wait for the checks to pass before merging.

## Build and publish

Local builds need Docker, Git, Python 3.11+, and `zstd`. The build runs as a generic
unprivileged user in an Arch container and installs dependencies there.

```bash
./install.sh --build-only orca
python scripts/repository.py build --repo filippov-au/arch-packages
```

Use an empty `dist/` directory for a complete repository build. Unchanged recipes
reuse checksum-verified published archives. Changed recipes build from scratch.
Bump `pkgrel` when modifying a recipe without changing its upstream version;
publishing refuses to replace an existing package filename with different bytes.

To publish a locally assembled repository using an existing `gh` login:

```bash
python scripts/repository.py publish --repo filippov-au/arch-packages
```

Keep the `packages` release mutable: its database and manifest are updated in
place. Package archives themselves are never overwritten.

## Privacy and validation

Only package source files and repository tooling belong in Git. Keep build
directories, downloaded binaries, output archives, environment files, and private
keys out of Git. Preserve upstream maintainer attribution and license notices.

Builds must receive only tracked/unignored package inputs, with no host home
directory, Git credentials, Docker socket, or token environment passed into the
container. Use generic `/build` paths in build metadata.

```bash
python scripts/audit.py --history
python scripts/audit.py --packages dist
python -m unittest discover -s tests -v
```

The source check looks for common credential patterns and personal home paths in
files and Git history. Package checks verify neutral build paths and root archive
ownership, and scan payloads for the build host's home path and hostname. These
checks supplement review; they are not a guarantee that arbitrary third-party
software contains no sensitive-looking data.

Git author names/emails are public. Keep GitHub authentication in the local CLI or
the runner's temporary environment, never in committed files or package artifacts.
