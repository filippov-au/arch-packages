# Daily Arch packages

Local, reviewed AUR PKGBUILDs for the apps I use on Omarchy.

```bash
./install.sh
```

Install a subset:

```bash
./install.sh proton_pass
./install.sh orca
```

Build without installing:

```bash
./install.sh --build-only
```

| Directory      | AUR package            | Version | What you get                          |
|----------------|------------------------|---------|---------------------------------------|
| `proton_pass`  | `proton-pass-bin`      | 1.39.1  | Official Proton Pass desktop app      |
| `proton_mail`  | `proton-mail-bin`      | 1.13.4  | Official Proton Mail desktop app      |
| `proton_drive` | `proton-drive-cli-bin` | 0.8.0   | Official Proton Drive **CLI**         |
| `proton_vpn`   | `proton-vpn-gtk-app`   | 4.16.5  | Official Proton VPN GTK app           |
| `orca`         | `stably-orca-bin`      | 1.4.188 | Official Orca ADE (prebuilt AppImage) |

Proton has no Linux Drive desktop client yet. `proton-drive` installs the official `proton-drive` command. After install: `proton-drive auth login`.

AUR `proton-vpn-gtk-app` is abandoned at 4.8.1 (the package moved to extra). `proton_vpn` tracks **extra 4.16.5**, which matches extra’s Python stack (`python-proton-vpn-api-core` 5.2.5). Extra-testing’s 4.17.2 needs `python-proton-vpn-api-core` ≥ 5.5.5 (extra-testing has 5.5.11) and dies on extra 5.2.5 with `ProtonVPNAPI.__init__() got an unexpected keyword argument 'locale'`. After install: `protonvpn-app`.

Orca ADE is [onorca.dev](https://www.onorca.dev/). After install: `stably-orca`.

## Safety notes (reviewed 2026-08-26)

Pass, Mail, Drive, and Orca are `-bin` packages: they wrap official upstream binaries and do not run `yarn` / `bun` / `cargo` at build time.

- **PKGBUILDs** only extract or install files. No `curl | sh`, no extra network in `package()`, no `sudo`.
- **Proton Pass** SHA-512 matches Proton's published `version.json`.
- **Proton Mail** uses Proton's `.deb` plus a 2-line wrapper around system `electron40`.
- **Proton Drive** installs Proton's official `proton-drive` binary from `proton.me`.
- **Proton VPN** is Python/GTK, not a `-bin` wrapper. The AUR leftover was 4.8.1; this tree is extra 4.16.5 (`python -m build`, no extra network in `package()`). Do not bump to extra-testing 4.17.2 unless extra’s `python-proton-vpn-api-core` is also ≥ 5.5.5.
- **Orca** is AUR `stably-orca-bin` (the name Orca documents). It extracts the official `orca-linux.AppImage` into `/opt/stably-orca` and launches `AppRun` — no AppImage at runtime. Command is `stably-orca` so it does not clash with GNOME’s `orca` screen reader. The local wrapper adds `--ozone-platform=wayland` for Hyprland; drop that flag in `orca/stably-orca.sh` to fall back to XWayland.

The source AUR variant `proton-pass` was **not** used: it is flagged out of date with a checksum mismatch.

Do not use AUR `orca` / `orca-git` (GNOME screen reader) or `orca-slicer*` (3D printer slicer). Other Orca ADE AUR names: `onorca-bin` (official `.deb`, also fine), `orca-ide-bin` (system Electron + asar rewrite, skip), `stably-orca` / `stably-orca-git` (source builds).

Re-read each `PKGBUILD` before you bump a version. AUR is still user-submitted.

## Update a package from the AUR

```bash
git clone --depth 1 "$(cat proton_pass/.aur-url)" /tmp/proton-pass-bin
# review PKGBUILD, then copy files back into ./proton_pass
```
