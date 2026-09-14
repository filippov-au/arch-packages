#!/usr/bin/env bash
# Build only tracked package inputs, without host credentials or home mounts.
set -euo pipefail
cd "$(dirname "$0")/.."
package=${1:?Usage: scripts/build.sh PACKAGE [OUTPUT_DIRECTORY]}
case "$package" in orca|proton_pass|proton_mail|proton_drive|proton_vpn) ;; *) exit 2 ;; esac
output=$(realpath -m "${2:-dist}")
mkdir -p "$output"
context=$(mktemp -d)
trap 'rm -rf "$context"' EXIT
mkdir "$context/package"
while IFS= read -r -d '' file; do
  [[ -f "$file" ]] || continue
  [[ $(realpath "$file") == "$(pwd)/$package/"* ]] || { echo 'Input escapes package directory' >&2; exit 1; }
  relative=${file#"$package/"}
  mkdir -p "$context/package/$(dirname "$relative")"
  cp "$file" "$context/package/$relative"
done < <(git ls-files --cached --others --exclude-standard -z -- "$package/")
cp scripts/container-build.sh "$context/build.sh"
chmod -R a+rX "$context"
# No Docker socket, host home, git credentials, or environment tokens are mounted.
docker run --rm --platform linux/amd64 \
  --mount "type=bind,source=$context,target=/input,readonly" \
  --mount "type=bind,source=$output,target=/output" \
  archlinux:base-devel bash /input/build.sh
python scripts/audit.py --packages "$output"
