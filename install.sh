#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
build_only=0
selected=()
while (($#)); do
  case "$1" in
    --build-only) build_only=1 ;;
    -h|--help)
      echo 'Usage: ./install.sh [--build-only] [orca proton_pass proton_mail proton_drive]'
      echo 'Without package names, prompts for packages to install (--build-only builds all).'
      exit 0 ;;
    orca|stably-orca|stably-orca-bin) selected+=(orca) ;;
    proton_pass|proton-pass-bin) selected+=(proton_pass) ;;
    proton_mail|proton-mail-bin) selected+=(proton_mail) ;;
    proton_drive|proton-drive-cli-bin) selected+=(proton_drive) ;;
    *) echo "Unknown option or package: $1" >&2; exit 2 ;;
  esac
  shift
done
if ((build_only)); then
  ((${#selected[@]})) || selected=(orca proton_pass proton_mail proton_drive)
  for package in "${selected[@]}"; do
    bash scripts/build.sh "$package" "dist/$package"
  done
  exit 0
fi
if ((${#selected[@]} == 0)); then
  printf '%s\n' 'Which packages would you like to install?' \
    '  1) Orca ADE' \
    '  2) Proton Pass' \
    '  3) Proton Mail' \
    '  4) Proton Drive CLI'
  while true; do
    printf 'Enter numbers separated by spaces (e.g. 1 2), all, or q to cancel: '
    if ! IFS= read -r answer || [[ -z ${answer//[[:space:]]/} || $answer == q ]]; then
      echo 'Installation cancelled.'
      exit 0
    fi
    choices=()
    read -r -a choices <<< "$answer"
    selected=()
    valid=1
    for choice in "${choices[@]}"; do
      case "$choice" in
        1) package=orca ;;
        2) package=proton_pass ;;
        3) package=proton_mail ;;
        4) package=proton_drive ;;
        all)
          if ((${#choices[@]} == 1)); then
            selected=(orca proton_pass proton_mail proton_drive)
            break
          fi
          valid=0; break ;;
        *) valid=0; break ;;
      esac
      if [[ " ${selected[*]} " != *" $package "* ]]; then
        selected+=("$package")
      fi
    done
    if ((valid)); then break; fi
    echo 'Invalid selection. Choose numbers from 1 to 4, all, or q.' >&2
  done
fi
declare -A names=(
  [orca]=stably-orca-bin
  [proton_pass]=proton-pass-bin
  [proton_mail]=proton-mail-bin
  [proton_drive]=proton-drive-cli-bin
)
targets=()
for package in "${selected[@]}"; do targets+=("arch-packages/${names[$package]}"); done
backend=$(python scripts/system.py)
sudo python scripts/enable-repo.py
if [[ $backend == omarchy ]]; then
  echo 'Detected Omarchy: updating through omarchy update before installing packages.'
  omarchy update -y
  # This explicit install reinstalls equal versions without requesting another
  # system upgrade. Omarchy already handled synchronization and migrations.
  sudo pacman -S "${targets[@]}"
else
  echo 'Detected Arch Linux: updating and installing through pacman.'
  sudo pacman -Syu "${targets[@]}"
fi
