# Contributing

Report packaging and installer problems in [GitHub Issues](https://github.com/filippov-au/arch-packages/issues).
Include the package name and version, distribution, desktop/session type, steps to
reproduce, expected behavior, and relevant error output. Remove credentials and
personal paths from logs before posting. For application bugs that also occur with
the upstream release, report them to the application project linked in its `PKGBUILD`.

## Package changes

1. Keep a pull request focused on one package or one tooling fix.
2. Preserve upstream maintainer attribution and license notices.
3. Review source URLs, checksums, dependencies, and install behavior. `PKGBUILD`
   files execute shell commands during builds.
4. Bump `pkgrel` when changing a recipe or bundled launcher without changing
   `pkgver`. Published package filenames cannot be replaced with different bytes.
5. Update `.SRCINFO` to match the recipe. In a disposable Arch build environment,
   run `makepkg --printsrcinfo > .SRCINFO` from the package directory.
6. Update checksums when changing files listed in `source`. `.upstream.json`
   configures the official vendor feed and asset selection; update it when the
   vendor changes its release format or supported downloads.

To prepare a verified update from the latest stable vendor release locally:

```bash
python scripts/update.py orca
```

## Validation

Run the lightweight checks with Python 3.11+ and Git:

```bash
python -m unittest discover -s tests -v
python scripts/audit.py --history
for file in install.sh scripts/*.sh orca/*.sh proton_mail/*.sh; do bash -n "$file"; done
git diff --check
```

For package changes, also build the affected package with Docker and `zstd` installed:

```bash
./install.sh --build-only orca
```

This builds and audits the package without installing it on your machine. Include
the commands run and their results in your pull request, including any checks you
could not complete. Keep downloaded sources, package archives, and local build
directories out of Git.

Before merging an automated update PR, review the changed recipe and approve any
pending workflow runs. Wait for validation and all package builds to pass. See the
[README](README.md#update-pull-requests) for the update and publishing workflows.
