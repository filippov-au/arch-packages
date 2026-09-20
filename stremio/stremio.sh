#!/usr/bin/env bash
# Native equivalent of the upstream Flatpak launcher and environment.
export LC_NUMERIC=C
export SERVER_PATH=/usr/lib/stremio/server.js
if [[ -e /dev/nvidia0 && -z ${GSK_RENDERER:-} ]]; then
  export GSK_RENDERER=opengl
fi
exec /usr/lib/stremio/stremio "$@"
