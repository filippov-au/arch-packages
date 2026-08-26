#!/usr/bin/env bash
# Build and install the local AUR packages in this repo.
#
#   ./install.sh                 # build + install everything
#   ./install.sh proton_pass     # one package (proton_pass, proton_mail, proton_drive, proton_vpn, orca)
#   ./install.sh --build-only    # build packages, do not install
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# directory -> pacman package name
declare -A PKGNAME=(
  [proton_pass]=proton-pass-bin
  [proton_mail]=proton-mail-bin
  [proton_drive]=proton-drive-cli-bin
  [proton_vpn]=proton-vpn-gtk-app
  [orca]=stably-orca-bin
)

ALL_PACKAGES=(proton_pass proton_mail proton_drive proton_vpn orca)

usage() {
  cat <<EOF
Usage: $(basename "$0") [options] [package ...]

Build the local PKGBUILDs with makepkg and install them with pacman.

Packages:
  proton_pass   Proton Pass desktop (proton-pass-bin 1.39.1)
  proton_mail   Proton Mail desktop (proton-mail-bin 1.13.4)
  proton_drive  Proton Drive CLI (proton-drive-cli-bin 0.8.0)
  proton_vpn    Proton VPN GTK app (proton-vpn-gtk-app 4.16.5)
  orca          Orca ADE desktop (stably-orca-bin 1.4.188)

Options:
  --build-only   Build packages but do not install
  -h, --help     Show this help

Examples:
  $(basename "$0")
  $(basename "$0") proton_pass
  $(basename "$0") --build-only proton_mail
EOF
}

normalize() {
  local name="${1//-/_}"
  case "$name" in
    stably_orca|stably_orca_bin) name=orca ;;
  esac
  case "$name" in
    proton_pass|proton_mail|proton_drive|proton_vpn|orca) printf '%s\n' "$name" ;;
    *)
      echo "Unknown package: $1" >&2
      echo "Known packages: ${ALL_PACKAGES[*]}" >&2
      exit 1
      ;;
  esac
}

build_only=0
selected=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --build-only)
      build_only=1
      shift
      ;;
    --)
      shift
      selected+=("$@")
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      selected+=("$(normalize "$1")")
      shift
      ;;
  esac
done

if [[ ${#selected[@]} -eq 0 ]]; then
  selected=("${ALL_PACKAGES[@]}")
fi

if ! command -v makepkg >/dev/null 2>&1; then
  echo "makepkg not found. Install base-devel first:" >&2
  echo "  sudo pacman -S --needed base-devel" >&2
  exit 1
fi

built_pkgs=()

for pkg in "${selected[@]}"; do
  dir="$ROOT/$pkg"
  if [[ ! -f "$dir/PKGBUILD" ]]; then
    echo "Missing PKGBUILD in $dir" >&2
    exit 1
  fi

  echo "==> Building $pkg (${PKGNAME[$pkg]})"
  (
    cd "$dir"
    makepkg -sf --needed --noconfirm --cleanbuild
  )

  # Use this PKGBUILD's packagelist, not every leftover *.pkg.tar.* in the dir.
  # A previous version (e.g. extra-testing 4.17.2 next to extra 4.16.5) makes
  # pacman -U fail with "duplicate target".
  found=0
  while IFS= read -r artifact; do
    [[ -f "$artifact" ]] || continue
    if [[ "$artifact" == *-debug-* ]]; then
      continue
    fi
    built_pkgs+=("$artifact")
    found=1
  done < <(cd "$dir" && makepkg --packagelist)

  if [[ $found -eq 0 ]]; then
    echo "No package artifact produced for $pkg" >&2
    exit 1
  fi
done

if [[ $build_only -eq 1 ]]; then
  echo
  echo "Built:"
  printf '  %s\n' "${built_pkgs[@]}"
  echo "Install later with:"
  echo "  sudo pacman -U ${built_pkgs[*]}"
  exit 0
fi

echo
echo "==> Installing"
sudo pacman -U --needed "${built_pkgs[@]}"
echo
echo "Done."
