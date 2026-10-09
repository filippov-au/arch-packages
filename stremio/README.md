# Local playback patches

`1.2.1-3` introduced a tested local fix for workspace-return stutter. Keep the
upstream CPU idle fix and the existing native idle inhibitor.

## Rendering

The GTK thread renders video and processes libmpv events. Synchronous commands
and property writes can block it while libmpv waits for rendering. Use the
asynchronous client APIs and receive their replies on a separate mpv client
handle sharing the same core. Since 1.2.2, upstream's player event loop reports
any raw mpv error as a failed stream; a rejected property write or command
reply there would end playback. Reply errors are logged only, matching the
previous synchronous behavior. See the [libmpv threading contract](https://github.com/mpv-player/mpv/blob/master/include/mpv/render.h).

When GDK reports a suspended/minimized surface, acknowledge new video frames
with `MPV_RENDER_PARAM_SKIP_RENDERING` instead of drawing them. For compositors
that do not report suspension, a single 100 ms timeout acknowledges an undrawn
frame. Successful GTK rendering cancels that timeout; no timer runs while idle.
Keep audio playing. Render calls do not wait for the target time because the
shell already sets `video-timing-offset=0`.

The local renderer uses stack parameters and retains its update callback until
libmpv rendering is shut down. It uses the same OpenGL/Wayland context as upstream.

## Hardware decoding default

Normal launches translate the UI's automatic `auto-copy` request to mpv's
`auto` policy, allowing direct decoding when supported. Explicit decoder
selections and disabled hardware decoding are preserved. mpv selects from its
supported decoder list and can fall back when a method is unavailable.

To restore the upstream copying policy for a session, close all Stremio
instances and run:

```bash
STREMIO_HWDEC=auto-copy stremio
```

`STREMIO_HWDEC=auto` also remains supported. These overrides apply only to the
UI's automatic policy; they do not enable hardware decoding when it is disabled
or replace an explicitly selected decoder. They work with both native shell and
D-Bus launches when the environment is present in the launching process.

## Validation

The package check runs headless libmpv integration tests for asynchronous command
and string argument ownership. They do not verify GTK/Wayland playback.

For runtime validation, use the same video, audio track, subtitles, display
brightness and refresh rate. Compare normal playback and at least three
workspace switches, including a 10-second absence. Check smooth return,
continuous audio, pause/seek controls and absence of repeated render-stall
warnings after returning. Compare CPU and battery power over 20 seconds with and without
`STREMIO_HWDEC=auto-copy`; confirm the actual decoder in the log. Also test
window closure/reopening and playback completion.

The recorded upstream behavior was hardware decoding with `vaapi-copy`, repeated
`mpv_render_context_render() not being called or stuck` warnings, and A/V drift
up to 0.48 seconds. The first patched playback/workspace-switch test reported smooth return, no
render-stall warnings, no reported dropped frames, and maximum A/V drift of
0.003 seconds across 708 status samples, still using `vaapi-copy`. This is one
manual test, not broad GTK/backend coverage. A subsequent 20.9-second direct-decoding test on the same 4K HDR video used
`vaapi` (without copy), with 19.1% total Stremio CPU, 2.8% mpv core CPU and
6.93 W average battery power. The window was visible throughout; brightness
was 218/496, refresh rate 120 Hz and the power profile balanced. No render-stall
warnings were recorded and maximum A/V drift was 0.001 seconds. The earlier
unpatched 1.2.1 measurement used approximately 82% CPU and 10.6 W; this compares
the combined rendering patch and direct-decoding mode, not an isolated decoding
benchmark. Direct decoding is now the default for the automatic policy; the copy-mode
override remains available for other codecs/backends.
Do not include playback logs or stream URLs in Git.
