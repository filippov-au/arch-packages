# Stremio packaging review

Reviewed 2026-09-20 against:

- [AUR stremio](https://aur.archlinux.org/packages/stremio), using the
  [official AUR mirror](https://github.com/archlinux/aur/blob/stremio/PKGBUILD)
  because the AUR web interface blocked automated access.
- [The AUR build patch](https://github.com/archlinux/aur/blob/stremio/010-stremio-do-not-download-server-js.patch).
- [Official Linux shell release 1.2.0](https://github.com/Stremio/stremio-linux-shell/releases/tag/v1.2.0)
  and its source, Cargo.lock, launcher, and Flatpak manifest.
- [Upstream's announcement of the current Linux app](https://blog.stremio.com/stremio-tech-update-81-stremio-v5-released-for-linux/).

The AUR recipe is maintained by Daniel Bermond and builds the legacy 4.4.183
Qt5 shell, with separately pinned 4.4.172 server.js and stremio.asar downloads.
Its patch removes the makefile's implicit server download. The shell tag and
server files have SHA-256 checksums. Two Git submodule sources use SKIP; their
checked-out revisions are selected by the shell's submodule references. The
recipe needs qt5-webengine and other Qt5 components and does not package the
current GTK4 shell. No install hook or privileged host modification was found
in the reviewed recipe and patch. This is a packaging review, not an audit of
Stremio's application code or hosted interface.

This repository independently packages upstream's current Linux shell under
`stremio-linux-shell`, with `stremio` as its command and an unversioned provides.
The separate package name avoids treating shell version 1.2.0 as a downgrade
from legacy application version 4.4.183. Pacman conflicts prevent overlapping
Stremio launchers from being installed together. Existing user data is not
modified by the package.

The source archive includes the streaming server and GPL license; neither is
downloaded from an unversioned URL during the build. Cargo fetch uses the
upstream lockfile; compilation uses --frozen. The archive and local launcher
have SHA-256 pins. GitHub publishes no independent checksum for its generated
source archives, so updates hash the official versioned HTTPS download rather
than claiming independent vendor checksum verification. Binary-package checksum
verification remains required for the other packages.

Native integration installs the application, server, desktop entry, D-Bus
service, icon, GSettings schema, metadata, translations, and upstream license.
The launcher sets the server path and numeric locale required by mpv and retains
upstream's NVIDIA OpenGL renderer workaround. Translation and D-Bus paths are
adapted from Flatpak to /usr; Arch's standard hooks compile the GSettings schema.
GTK4, libadwaita, WebKitGTK, mpv, Node.js, and libepoxy come from Arch repositories.
The package does not embed a Flatpak runtime or change desktop/system settings.

The UI is served by upstream's web service, as in the official Linux shell, so
pinning the native package does not pin the hosted interface or user add-ons.
