#!/usr/bin/env bash
set -euo pipefail
pacman -Syu --noconfirm --needed git sudo
useradd --create-home --home-dir /build builder
printf 'builder ALL=(ALL) NOPASSWD: /usr/bin/pacman\n' >/etc/sudoers.d/builder
cp -r /input/package /build/package
chown -R builder:builder /build
cat >> /etc/makepkg.conf <<'EOF'
PACKAGER='Arch Packages Builder'
PKGDEST=/build/output
BUILDDIR=/build/work
OPTIONS+=('!debug')
EOF
mkdir /build/output
chown builder:builder /build/output
cd /build/package
# Recipes pin release signing keys by fingerprint; import the reviewed public keys.
if compgen -G 'keys/pgp/*.asc' >/dev/null; then
  sudo -u builder gpg --batch --import keys/pgp/*.asc
fi
sudo -u builder makepkg --syncdeps --noconfirm --cleanbuild
cp /build/output/*.pkg.tar.zst /output/
chmod a+r /output/*.pkg.tar.zst
