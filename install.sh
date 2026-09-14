#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
build_only=0
selected=()
while (($#)); do
  case "$1" in
    --build-only) build_only=1 ;;
    -h|--help)
      echo 'Usage: ./install.sh [--build-only] [orca proton_pass proton_mail proton_drive proton_vpn]'
      exit 0 ;;
    orca|stably-orca|stably-orca-bin) selected+=(orca) ;;
    proton_pass|proton-pass-bin) selected+=(proton_pass) ;;
    proton_mail|proton-mail-bin) selected+=(proton_mail) ;;
    proton_drive|proton-drive-cli-bin) selected+=(proton_drive) ;;
    proton_vpn|proton-vpn-gtk-app) selected+=(proton_vpn) ;;
    *) echo "Unknown option or package: $1" >&2; exit 2 ;;
  esac
  shift
done
((${#selected[@]})) || selected=(orca proton_pass proton_mail proton_drive proton_vpn)
if ((build_only)); then
  for package in "${selected[@]}"; do
    bash scripts/build.sh "$package" "dist/$package"
  done
  exit 0
fi
declare -A names=(
  [orca]=stably-orca-bin
  [proton_pass]=proton-pass-bin
  [proton_mail]=proton-mail-bin
  [proton_drive]=proton-drive-cli-bin
  [proton_vpn]=proton-vpn-gtk-app
)
targets=()
for package in "${selected[@]}"; do targets+=("arch-packages/${names[$package]}"); done
sudo python scripts/enable-repo.py
sudo pacman -Syu "${targets[@]}"
