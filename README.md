# Daily Arch packages

Local, reviewed AUR PKGBUILDs for the apps I use on Omarchy.

```bash
./install.sh
```

Install a subset:

```bash
./install.sh proton_pass
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

Proton has no Linux Drive desktop client yet. `proton-drive` installs the official `proton-drive` command. After install: `proton-drive auth login`.

AUR `proton-vpn-gtk-app` is abandoned at 4.8.1 (the package moved to extra). `proton_vpn` tracks **extra 4.16.5**, which matches extra’s Python stack (`python-proton-vpn-api-core` 5.2.5). Extra-testing’s 4.17.2 needs `python-proton-vpn-api-core` ≥ 5.5.5 (extra-testing has 5.5.11) and dies on extra 5.2.5 with `ProtonVPNAPI.__init__() got an unexpected keyword argument 'locale'`. After install: `protonvpn-app`.

## Safety notes (reviewed 2026-08-22)

Pass, Mail, and Drive are `-bin` packages: they wrap official upstream binaries and do not run `yarn` / `bun` / `cargo` at build time.

- **PKGBUILDs** only extract or install files. No `curl | sh`, no extra network in `package()`, no `sudo`.
- **Proton Pass** SHA-512 matches Proton's published `version.json`.
- **Proton Mail** uses Proton's `.deb` plus a 2-line wrapper around system `electron40`.
- **Proton Drive** installs Proton's official `proton-drive` binary from `proton.me`.
- **Proton VPN** is Python/GTK, not a `-bin` wrapper. The AUR leftover was 4.8.1; this tree is extra 4.16.5 (`python -m build`, no extra network in `package()`). Do not bump to extra-testing 4.17.2 unless extra’s `python-proton-vpn-api-core` is also ≥ 5.5.5.

The source AUR variant `proton-pass` was **not** used: it is flagged out of date with a checksum mismatch.

Re-read each `PKGBUILD` before you bump a version. AUR is still user-submitted.

## Update a package from the AUR

```bash
git clone --depth 1 "$(cat proton_pass/.aur-url)" /tmp/proton-pass-bin
# review PKGBUILD, then copy files back into ./proton_pass
```
