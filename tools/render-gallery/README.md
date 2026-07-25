# Render gallery — see ComfyUI output from your phone

A one-file web gallery for ComfyUI's output folder, meant to be pinned to a phone
home screen. Stdlib only — no `pip install`. Read-only: it never writes to or
deletes from the output folder.

Why not just use ComfyUI's own UI? You can (`http://<tailscale-ip>:8000`), but its
queue history is painful on a small screen. This is a plain grid, newest first.

## Run it on the PC

```
cd C:\Users\GH-DA\mobile-work\tools\render-gallery
python server.py
```

It auto-detects `C:\Users\GH-DA\ComfyUI-Shared\output`, falling back to a couple of
other common spots. Override with `--dir <path>` or `set COMFY_OUTPUT=<path>`.
`gallery.cmd` does the same thing in one tap — save it as a Termius snippet.

On start it prints the URLs that will work from the phone; the `100.x.x.x` one is
Tailscale. It binds `0.0.0.0` so the tailnet can reach it.

## Pin it to the home screen

Open the Tailscale URL on the phone, then:

- **iOS / Safari** — Share → Add to Home Screen
- **Android / Chrome** — ⋮ → Add to Home screen / Install app

You get a gold-star icon and it opens fullscreen, without browser chrome.

## What it does

- Newest-first grid, including images saved into subfolders
- New renders since you opened it get a **new** badge; the list polls every 8s and
  refreshes whenever you switch back to the app
- Tap an image for the full-size view plus the settings pulled out of the PNG —
  model, seed, steps, cfg, sampler, dimensions, and the positive prompt (ComfyUI
  embeds the workflow in a `tEXt` chunk, which this parses)
- Filter box matches on filename, handy for `MageKaarten` vs `steptest`
- Thumbnails are generated with Pillow when it's importable — run it with
  ComfyUI's Python to get that. Without Pillow it still works, just sends full
  images and takes longer over a phone connection.

## Scope

Serves over plain HTTP with no auth, so keep it on Tailscale. Don't point ngrok or
a Cloudflare tunnel at this port without putting a password in front of it —
anything on the tailnet can read every image in the output folder. Path traversal
outside the output folder is refused, but that's the only access control here.
