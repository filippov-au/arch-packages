# Arch packages

Reviewed Arch Linux packages for Orca ADE, Proton Pass, Proton Mail, Proton Drive CLI, and Proton VPN.

- **Source:** https://github.com/filippov-au/arch-packages
- **Hosted pacman repository:** [GitHub Releases](https://github.com/filippov-au/arch-packages/releases/tag/packages)
- **Updates:** daily checks open a separate pull request for each changed package.
- **Publishing:** merging to `master` builds changed recipes and updates the hosted repository.

## Install on an Arch Linux machine

Clone this repository and run:

```bash
git clone https://github.com/filippov-au/arch-packages.git
cd arch-packages
./install.sh
```

Or install a subset:

```bash
./install.sh orca proton_pass
```

The installer backs up `/etc/pacman.conf`, puts this repository before Arch's
repositories, and detects the system automatically:

- **Omarchy:** runs `omarchy update -y` for the full update workflow, including
  snapshots and migrations, then `sudo pacman -S` for the selected packages.
- **Arch Linux:** runs `sudo pacman -Syu` with the selected packages as targets.

Detection uses `/etc/os-release` and the `omarchy` command, including older Omarchy
installations that identify as Arch. Failed updates stop the installer before the
package installation step. Omarchy's `-y` runs its update without additional
confirmation prompts; the final package installation still asks for confirmation.
Explicit targets reinstall an equal version too, so an existing AUR Orca
installation gets the customized launcher.

For manual configuration, add this **above `[core]` and `[extra]`**, outside the
`[options]` section:

```ini
[arch-packages]
SigLevel = Optional TrustAll
Server = https://github.com/filippov-au/arch-packages/releases/download/packages
```

On **Omarchy**, update through its normal entrypoint, then install Orca:

```bash
omarchy update
sudo pacman -S arch-packages/stably-orca-bin
```

On **Arch Linux**, update and install Orca together:

```bash
sudo pacman -Syu arch-packages/stably-orca-bin
```

Downloads are public and need no account or token. Packages currently have no
package signatures; trust relies on GitHub HTTPS and repository write access.
The signature setting above applies only to this repository. Official Arch
repositories retain their existing signature requirements.

Pacman prefers the first repository containing the same package name. Once this
repository is configured and its database is refreshed, normal Yay AUR updates
exclude these repository packages. Your reviewed releases control their updates.
Do not add these packages to `IgnorePkg`: that would also block your own updates.
Do not use `-Suu` to force downgrades when your installed version is newer.

## Packages

| Directory | Package name | Source of packaging updates |
|---|---|---|
| `orca` | `stably-orca-bin` | AUR |
| `proton_pass` | `proton-pass-bin` | AUR |
| `proton_mail` | `proton-mail-bin` | AUR |
| `proton_drive` | `proton-drive-cli-bin` | AUR |
| `proton_vpn` | `proton-vpn-gtk-app` | Arch's official packaging repository |

See each `PKGBUILD` for its version, dependencies, checksums, and upstream license.
The published binary repository targets **x86_64** machines, including packages
marked `any`. It does not currently publish a separate ARM repository.

Orca uses the extracted official AppImage, sets `APPDIR`, disables Vulkan, and
forces native Wayland. Its command is `stably-orca`; GNOME's `orca` package is an
unrelated screen reader. Proton Drive is the official CLI, not a desktop client.
Proton VPN follows Arch's maintained recipe, not its abandoned AUR entry.

## Update pull requests

The **Check package updates** workflow runs daily and can also be started from
GitHub's Actions tab. It checks each package independently and opens one PR per
upstream packaging revision. Existing PRs for the same revision are not duplicated.
There is no automatic merge.

The script uses each package's `.upstream.json` to merge the previous upstream
recipe, your local recipe, and the new upstream recipe. This preserves changes
such as Orca's Wayland launcher and its checksum. Conflicting changes fail that
package's job without modifying files; they require a manual merge. Updates to
upstream applications appear when the tracked AUR/Arch recipe is updated.

Run an update locally without creating a PR:

```bash
python scripts/update.py orca
```

Or open a PR from a **clean checkout of the latest `master`** using your existing
GitHub CLI login:

```bash
python scripts/update.py orca --pr --repo filippov-au/arch-packages
```

PR mode switches the checkout to its update branch. The scheduled workflow gives
each package a separate checkout. Review the recipe, source URLs, checksums,
dependency changes, and build results before merging. If GitHub asks for approval
before running a bot-created PR's checks, select **Approve workflows to run**.

GitHub Actions must have **Allow GitHub Actions to create and approve pull requests**
enabled in Settings → Actions → General. The workflow uses the temporary built-in
`GITHUB_TOKEN`; no personal access token or repository secret is required.

## Build and publish

Local builds need Docker, Git, Python 3.11+, and `zstd`. The build runs as a generic
unprivileged user in an Arch container. It installs dependencies in that container.

```bash
./install.sh --build-only orca
python scripts/repository.py build --repo filippov-au/arch-packages
```

Use an empty `dist/` directory for a complete repository build. Unchanged recipes
reuse checksum-verified published archives. Changed recipes build from scratch.
Bump `pkgrel` when modifying a recipe without changing its upstream version;
publishing refuses to replace an existing package filename with different bytes.

The **Publish package repository** workflow runs after a push/merge to `master`
and supports manual dispatch. Its build job has read-only GitHub permissions.
A separate publishing job receives temporary release-write permission, uploads
new package files first, and updates the repository database last. Older package
archives remain downloadable for clients with an older database.

To publish a locally assembled repository using an existing `gh` login:

```bash
python scripts/repository.py publish --repo filippov-au/arch-packages
```

Keep the `packages` release mutable: its database and manifest are updated in
place. Package archives themselves are never overwritten. GitHub stores the
binaries as Release assets, not Git objects; no additional hosting service is needed.

## Privacy and validation

Only package source files and repository tooling belong in Git. Build directories,
downloaded binaries, output archives, environment files, and common private-key
files are ignored. Builds receive only tracked/unignored package inputs, with no
host home directory, Git credentials, Docker socket, or token environment passed
into the container. Build metadata uses generic `/build` paths.

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

Git author names/emails are public. Upstream maintainer attribution and license
notices are preserved. GitHub authentication remains in the local CLI or in the
runner's temporary environment, never in committed files or package artifacts.
