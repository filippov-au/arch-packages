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

Proton has no Linux Drive desktop client yet. `proton-drive` installs the official `proton-drive` command. After install: `proton-drive auth login`.

## Safety notes (reviewed 2026-08-20)

These are `-bin` packages: they wrap official upstream binaries and do not run `yarn` / `bun` / `cargo` at build time.

- **PKGBUILDs** only extract or install files. No `curl | sh`, no extra network in `package()`, no `sudo`.
- **Proton Pass** SHA-512 matches Proton's published `version.json`.
- **Proton Mail** uses Proton's `.deb` plus a 2-line wrapper around system `electron40`.
- **Proton Drive** installs Proton's official `proton-drive` binary from `proton.me`.

The source AUR variant `proton-pass` was **not** used: it is flagged out of date with a checksum mismatch.

Re-read each `PKGBUILD` before you bump a version. AUR is still user-submitted.

## Update a package from the AUR

```bash
git clone --depth 1 "$(cat proton_pass/.aur-url)" /tmp/proton-pass-bin
# review PKGBUILD, then copy files back into ./proton_pass
```
