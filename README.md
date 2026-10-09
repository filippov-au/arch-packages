# Arch packages

Reviewed Arch Linux packages for Proton Pass, Proton Mail, Proton Drive CLI, and Stremio.

This is a community-maintained pacman repository for **x86_64 Arch Linux and
Omarchy**. Packages are currently **unsigned**; see [Trust](#trust) before
installing.

- **Source:** https://github.com/filippov-au/arch-packages
- **Hosted repository:** [GitHub Releases](https://github.com/filippov-au/arch-packages/releases/tag/packages)
- **Updates:** daily checks open a separate pull request for each changed package.
- **Publishing:** merging to `master` builds changed recipes and updates the hosted repository.
- **Contributing:** [report issues and propose changes](CONTRIBUTING.md).

## Packages

| Directory | Package name | Release source |
|---|---|---|
| `proton_pass` | `proton-pass-bin` | Proton's Linux release feed |
| `proton_mail` | `proton-mail-bin` | Proton's Linux release feed |
| `proton_drive` | `proton-drive-cli-bin` | Proton's CLI release feed |
| `stremio` | `stremio-linux-shell` | Official GitHub source releases |

See each `PKGBUILD` for its version, dependencies, checksums, and upstream license.
Only **x86_64** is published, including packages marked `any`; there is no ARM
repository.

- **Proton Drive** is the official CLI, not a desktop client.
- **Stremio** builds the GTK4 Linux shell from source; its version is the shell's,
  not the hosted web interface's. The command is `stremio`. It provides and
  conflicts with the legacy AUR `stremio` Qt5 package, so pacman will offer to
  remove that package. See the [AUR and upstream review](stremio/REVIEW.md).

## Install

The installer needs only Bash and standard Arch tools. Run it without cloning:

```bash
curl -fsSL https://raw.githubusercontent.com/filippov-au/arch-packages/master/install.sh | bash
```

Or from a clone:

```bash
git clone https://github.com/filippov-au/arch-packages.git
cd arch-packages
./install.sh                     # choose interactively
./install.sh proton_pass stremio # or name packages directly
```

At the prompt, enter package numbers separated by spaces, or `all`. Enter `q` or
leave it blank to cancel.

The installer backs up `/etc/pacman.conf`, adds this repository before Arch's
repositories, forces a fresh package index (the hosted database is replaced in
place), and then updates the system:

- **Omarchy:** `omarchy update -y` (snapshots and migrations included), then
  `sudo pacman -S` for the selected packages.
- **Arch Linux:** `sudo pacman -Syyu` with the selected packages as targets.

Omarchy is detected from `/etc/os-release` and the `omarchy` command, including
older installations that identify as Arch. A failed update stops the installer
before packages are installed, and the final installation still asks for
confirmation. Explicit targets reinstall an equal version, so an existing AUR
installation of the same package is replaced by this repository's build.

### Manual setup

Add this **above `[core]` and `[extra]`**, outside the `[options]` section of
`/etc/pacman.conf`:

```ini
[arch-packages]
SigLevel = Optional TrustAll
Server = https://github.com/filippov-au/arch-packages/releases/download/packages
```

Then install a package:

```bash
# Omarchy
omarchy update
sudo pacman -S arch-packages/proton-pass-bin

# Arch Linux
sudo pacman -Syu arch-packages/proton-pass-bin
```

### Trust

Downloads are public and need no account or token. Packages have no signatures;
trust relies on GitHub HTTPS and repository write access. The `SigLevel` above
applies only to this repository; official Arch repositories keep their own
signature requirements.

Pacman prefers the first repository containing a package name, so once this
repository is configured, Yay's AUR updates skip these packages and this
repository controls their updates. Do not add them to `IgnorePkg` (that blocks
these updates too), and do not use `-Suu` to force downgrades when your installed
version is newer.

## Stremio playback patches

On top of upstream's idle CPU fix, the package carries three local patches:

- **Native idle inhibition:** uses GTK's Wayland idle inhibitor during playback
  when the desktop portal has no working Inhibit backend.
- **Non-blocking rendering:** sends mpv commands asynchronously so they cannot
  stall GTK rendering, and skips drawing suspended or minimized windows.
- **Direct hardware decoding:** changes the automatic `auto-copy` policy to mpv's
  `auto`, keeping GPU frames on the GPU when supported. Disabled or explicitly
  chosen decoders are unchanged.

To compare against upstream's copying policy, fully close Stremio and run:

```bash
STREMIO_HWDEC=auto-copy stremio
```

In one Intel/Wayland test with 4K HEVC HDR video, the patches removed
workspace-return stalls and cut Stremio CPU from ~82% to ~19% and laptop power
from 10.6 W to 6.9 W compared with upstream 1.2.1. Results depend on driver,
codec, and desktop. See [patch details and validation](stremio/README.md).

## Update pull requests

The **Check package updates** workflow runs daily (or manually from the Actions
tab) and checks each package in a separate checkout. It opens one PR per new
stable vendor version and closes older update PRs for the same package. It does
not duplicate existing PRs, reopen manually closed ones, or merge automatically.

Each package's `.upstream.json` names its official release feed and assets. The
updater picks the highest stable Proton version or the latest stable Stremio
GitHub release, never downgrades, and updates `pkgver`, `pkgrel`, checksums, and
`.SRCINFO`. It does not wait for AUR updates or import third-party packaging
changes; recipes, dependencies, and launchers are maintained here.

- Vendor-published checksums are verified, including both Drive architectures;
  Mail's launcher checksums (including BLAKE2) are preserved.
- Stremio source archives have no published checksum, so the updater pins the
  SHA-256 of the reviewed versioned HTTPS URL. Rust dependencies are locked by
  upstream's `Cargo.lock`.
- A changed download URL, missing asset, or checksum mismatch stops the update
  before files change. No `PKGBUILD` is executed during the check.
- Mail's build checks that its Electron dependency matches the application.

Packaging and dependency changes still need review. The workflow uses the
temporary built-in `GITHUB_TOKEN`, so no personal token or secret is needed, but
**Allow GitHub Actions to create and approve pull requests** must be enabled in
Settings → Actions → General.

## Build and publish

Builds run as a generic unprivileged user in an Arch container. Unchanged recipes
reuse checksum-verified published archives; changed recipes build from scratch.

The **Publish package repository** workflow runs after each push to `master` and
on manual dispatch. The build job has read-only permissions; a separate job with
temporary release-write permission publishes. Before uploading, it checks every
archive against the manifest and verifies that both databases and their `.db`/
`.files` aliases list matching packages, sizes, and checksums. It uploads new
package files first and the database last.

The `packages` release is mutable: its database and manifest are updated in place,
but package archives are never overwritten, and older archives stay downloadable
for clients with an older database. Binaries are stored as Release assets, not Git
objects.

## Privacy and validation

Build directories, downloaded binaries, output archives, environment files, and
common private-key files are ignored by Git. Builds receive only tracked/unignored
package inputs, with no host home directory, Git credentials, Docker socket, or
token environment, and use generic `/build` paths in metadata.

The source check scans files and Git history for common credential patterns and
personal home paths. Package checks verify neutral build paths and root archive
ownership, and scan payloads for the build host's home path and hostname. These
checks supplement review; they cannot guarantee that third-party software
contains no sensitive-looking data.

Git author names and emails are public. Upstream attribution and license notices
are preserved. GitHub authentication stays in the local CLI or the runner's
temporary environment, never in committed files or package artifacts.
