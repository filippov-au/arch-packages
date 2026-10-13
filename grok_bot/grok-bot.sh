#!/usr/bin/bash
# Optional Electron/Chromium flags, one or more per line; '#' starts a comment.
flags=()
config=${XDG_CONFIG_HOME:-$HOME/.config}/grok-bot-flags.conf
if [[ -r $config ]]; then
    read -r -d '' -a flags < <(sed 's/#.*//' "$config") || true
fi
exec /opt/grok-bot/grok-bot "${flags[@]}" "$@"
