#!/usr/bin/env bash

update_backend() {
  local release=${1:-/etc/os-release} key value distro_id= distro_like=
  local -a relatives=()
  while IFS='=' read -r key value || [[ -n $key ]]; do
    case "$key" in
      ID|ID_LIKE)
        value=${value%"${value##*[![:space:]]}"}
        case "$value" in
          \"*\") value=${value:1:${#value}-2} ;;
          \'*\') value=${value:1:${#value}-2} ;;
        esac
        if [[ $key == ID ]]; then distro_id=$value; else distro_like=$value; fi ;;
    esac
  done < "$release" || return 1

  # Older Omarchy installations identify as Arch in os-release.
  if [[ $distro_id == omarchy ]] || command -v omarchy >/dev/null 2>&1; then
    if ! command -v omarchy >/dev/null 2>&1; then
      echo 'Omarchy detected, but the omarchy command is missing' >&2
      return 1
    fi
    echo omarchy
    return 0
  fi
  read -r -a relatives <<< "$distro_like"
  if [[ $distro_id == arch || " ${relatives[*]} " == *' arch '* ]]; then
    if ! command -v pacman >/dev/null 2>&1; then
      echo 'Arch detected, but the pacman command is missing' >&2
      return 1
    fi
    echo pacman
    return 0
  fi
  echo 'This installer supports Arch Linux and Omarchy' >&2
  return 1
}

configure_repo() {
  awk '
    /^[[:space:]]*\[[^]]+\][[:space:]]*(#.*)?$/ {
      section = $0
      sub(/^[[:space:]]*\[/, "", section)
      sub(/\].*$/, "", section)
      if (!seen++ && section != "options") {
        invalid = 1
        exit 1
      }
      skip = (section == "arch-packages")
      if (!skip && section != "options" && !first_repo) first_repo = count + 1
    }
    !skip { lines[++count] = $0 }
    END {
      if (invalid || !seen) {
        print "Expected [options] as the first pacman.conf section" > "/dev/stderr"
        exit 1
      }
      if (!first_repo) first_repo = count + 1
      prefix_end = first_repo - 1
      while (prefix_end > 0 && lines[prefix_end] ~ /^[[:space:]]*$/) prefix_end--
      for (i = 1; i <= prefix_end; i++) print lines[i]
      print "\n[arch-packages]"
      print "SigLevel = Optional TrustAll"
      print "Server = https://github.com/filippov-au/arch-packages/releases/download/packages\n"
      for (i = first_repo; i <= count; i++) print lines[i]
    }
  '
}

enable_repo() (
  set -euo pipefail
  local config=${1:-/etc/pacman.conf} candidate backup
  candidate=$(mktemp "${config%/*}/.pacman.conf.XXXXXX")
  trap 'if [[ -e $candidate ]]; then rm -- "$candidate"; fi' EXIT
  configure_repo < "$config" > "$candidate"
  if cmp -s -- "$config" "$candidate"; then
    echo 'Repository already configured first.'
    return 0
  fi
  pacman-conf --config "$candidate" --repo-list
  backup=$(mktemp "$config.backup-$(date +%Y%m%d%H%M%S).XXXXXX")
  cp -p -- "$config" "$backup"
  chown --reference="$config" -- "$candidate"
  chmod --reference="$config" -- "$candidate"
  mv -- "$candidate" "$config"
  echo "Configured repository. Backup: $backup"
)

install_main() {
  set -euo pipefail
  build_only=0
  selected=()
  while (($#)); do
    case "$1" in
      --build-only) build_only=1 ;;
      -h|--help)
        echo 'Usage: ./install.sh [--build-only] [orca proton_pass proton_mail proton_drive stremio]'
        echo 'Without package names, prompts for packages to install (--build-only builds all).'
        exit 0 ;;
      orca|stably-orca|stably-orca-bin) selected+=(orca) ;;
      proton_pass|proton-pass-bin) selected+=(proton_pass) ;;
      proton_mail|proton-mail-bin) selected+=(proton_mail) ;;
      proton_drive|proton-drive-cli-bin) selected+=(proton_drive) ;;
      stremio|stremio-linux-shell) selected+=(stremio) ;;
      *) echo "Unknown option or package: $1" >&2; exit 2 ;;
    esac
    shift
  done
  if ((build_only)); then
    if [[ -z ${BASH_SOURCE[0]:-} ]]; then
      echo '--build-only requires a repository checkout.' >&2
      exit 2
    fi
    cd "$(dirname "${BASH_SOURCE[0]}")"
    ((${#selected[@]})) || selected=(orca proton_pass proton_mail proton_drive stremio)
    for package in "${selected[@]}"; do
      bash scripts/build.sh "$package" "dist/$package"
    done
    exit 0
  fi
  # Keep prompts and package manager input available with curl ... | bash.
  if [[ ! -t 0 && -t 1 ]]; then exec </dev/tty; fi
  if ((${#selected[@]} == 0)); then
    printf '%s\n' 'Which packages would you like to install?' \
      '  1) Orca ADE' \
      '  2) Proton Pass' \
      '  3) Proton Mail' \
      '  4) Proton Drive CLI' \
      '  5) Stremio'
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
          5) package=stremio ;;
          all)
            if ((${#choices[@]} == 1)); then
              selected=(orca proton_pass proton_mail proton_drive stremio)
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
      echo 'Invalid selection. Choose numbers from 1 to 5, all, or q.' >&2
    done
  fi
  declare -A names=(
    [orca]=stably-orca-bin
    [proton_pass]=proton-pass-bin
    [proton_mail]=proton-mail-bin
    [proton_drive]=proton-drive-cli-bin
    [stremio]=stremio-linux-shell
  )
  targets=()
  for package in "${selected[@]}"; do targets+=("arch-packages/${names[$package]}"); done
  backend=$(update_backend)
  sudo bash -c "$(declare -f configure_repo enable_repo)"$'\nenable_repo'
  if [[ $backend == omarchy ]]; then
    # Release database assets are replaced in place. Force a refresh so an
    # older local index cannot hide a newly published package.
    sudo pacman -Syy
    echo 'Detected Omarchy: updating through omarchy update before installing packages.'
    omarchy update -y
    # This explicit install reinstalls equal versions without requesting another
    # system upgrade. Omarchy already handled synchronization and migrations.
    sudo pacman -S "${targets[@]}"
  else
    echo 'Detected Arch Linux: updating and installing through pacman.'
    sudo pacman -Syyu "${targets[@]}"
  fi
}

if [[ -z ${BASH_SOURCE[0]:-} || ${BASH_SOURCE[0]} == "$0" ]]; then
  install_main "$@"
fi
