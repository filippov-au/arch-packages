# Arch packages

Reviewed Arch Linux packages for Orca ADE, Proton Pass, Proton Mail, and Proton Drive CLI.

This is a community-maintained package repository. The hosted packages target
**x86_64 Arch Linux and Omarchy**. Orca's customized launcher requires a Wayland
session. Packages are currently **unsigned**; see the trust details below before
installing.

- **Source:** https://github.com/filippov-au/arch-packages
- **Hosted pacman repository:** [GitHub Releases](https://github.com/filippov-au/arch-packages/releases/tag/packages)
- **Updates:** daily checks open a separate pull request for each changed package.
- **Publishing:** merging to `master` builds changed recipes and updates the hosted repository.
- **Contributing:** [report issues and propose changes](CONTRIBUTING.md).

## Install on an Arch Linux machine

Installation uses Bash and standard Arch system tools; Python is not required.

Run the standalone installer without cloning:

```bash
curl -fsSL https://raw.githubusercontent.com/filippov-au/arch-packages/master/install.sh | bash
```

Or clone this repository and run:

```bash
git clone https://github.com/filippov-au/arch-packages.git
cd arch-packages
./install.sh
```

The installer asks which packages to install. Enter their numbers separated by
spaces, or `all` to select every package. Enter `q` or leave the answer blank to
cancel.

Or select packages directly without the selection prompt:

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

| Directory | Package name | Release source |
|---|---|---|
| `orca` | `stably-orca-bin` | Official GitHub releases |
| `proton_pass` | `proton-pass-bin` | Proton's Linux release feed |
| `proton_mail` | `proton-mail-bin` | Proton's Linux release feed |
| `proton_drive` | `proton-drive-cli-bin` | Proton's CLI release feed |

See each `PKGBUILD` for its version, dependencies, checksums, and upstream license.
The published binary repository targets **x86_64** machines, including packages
marked `any`. It does not currently publish a separate ARM repository.

Orca uses the extracted official AppImage, sets `APPDIR`, disables Vulkan, and
forces native Wayland. Its command is `stably-orca`; GNOME's `orca` package is an
unrelated screen reader. Proton Drive is the official CLI, not a desktop client.

## Update pull requests

The **Check package updates** workflow runs daily and can also be started from
GitHub's Actions tab. It checks each package independently and opens one PR per
stable vendor version. Existing PRs for the same version are not duplicated.
There is no automatic merge.

Each package's `.upstream.json` identifies its official release feed and assets.
The checker downloads new stable releases, verifies vendor-published checksums,
and updates `pkgver`, `pkgrel`, source checksums, and `.SRCINFO`. It does not wait
for AUR updates or import third-party packaging changes. Recipes, dependencies,
and launchers are maintained here; existing attribution and license notices remain.

The updater selects the highest stable Proton version or Orca's latest stable
GitHub release, and never automatically downgrades. It verifies both Drive
architectures and preserves launcher checksums, including Mail's additional
BLAKE2 checksum. A changed download URL, missing asset, or checksum mismatch
stops the update before package files change. No `PKGBUILD` is executed during
the update check. Packaging and dependency changes need review; Mail's build
also checks that its Electron dependency matches the downloaded application.

The scheduled workflow gives each package a separate checkout.

GitHub Actions must have **Allow GitHub Actions to create and approve pull requests**
enabled in Settings → Actions → General. The workflow uses the temporary built-in
`GITHUB_TOKEN`; no personal access token or repository secret is required.

## Build and publish

The build runs as a generic unprivileged user in an Arch container and installs
dependencies there. Unchanged recipes reuse checksum-verified published archives;
changed recipes build from scratch.

The **Publish package repository** workflow runs after a push/merge to `master`
and supports manual dispatch. Its build job has read-only GitHub permissions.
A separate publishing job receives temporary release-write permission, uploads
new package files first, and updates the repository database last. Older package
archives remain downloadable for clients with an older database.

Before any release upload, the publisher checks every package archive against the
manifest, verifies that both databases list the same packages with matching sizes
and checksums, and verifies their `.db` and `.files` aliases. Missing or stale
database files stop publication before the release is modified.

The `packages` release is mutable: its database and manifest are updated in
place. Package archives themselves are never overwritten. GitHub stores the
binaries as Release assets, not Git objects; no additional hosting service is needed.

## Privacy and validation

Build directories, downloaded binaries, output archives, environment files, and
common private-key files are ignored. Builds receive only tracked/unignored
package inputs, with no host home directory, Git credentials, Docker socket, or
token environment passed into the container. Build metadata uses generic `/build`
paths.

The source check looks for common credential patterns and personal home paths in
files and Git history. Package checks verify neutral build paths and root archive
ownership, and scan payloads for the build host's home path and hostname. These
checks supplement review; they are not a guarantee that arbitrary third-party
software contains no sensitive-looking data.

Git author names/emails are public. Upstream maintainer attribution and license
notices are preserved. GitHub authentication remains in the local CLI or in the
runner's temporary environment, never in committed files or package artifacts.
