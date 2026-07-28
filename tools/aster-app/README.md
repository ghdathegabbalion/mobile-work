# Aster app — talk to Aster and render from your phone

A one-file web app for the PC, meant to be pinned to a phone home screen. Three
tabs: **Chat** with Aster, **Render** on the PC's GPU, **Gallery** of what came
out. Stdlib only — no `pip install`.

Aster keeps running on the PC; this is just a front end for it over Tailscale.
Chat and rendering are wired together: when ComfyUI is up, Aster is told it may
ask for a picture, and the images come back in the chat thread.

## Run it on the PC

```
cd C:\Users\GH-DA\mobile-work\tools\aster-app
python server.py
```

`aster.cmd` does the same in one tap — save it as a Termius snippet. It prints
the URLs that work from the phone; the `100.x.x.x` one is Tailscale.

**Start here if anything looks wrong:**

```
python server.py --probe
```

That changes nothing and reports what it can actually reach — which chat backend
it resolved, whether ComfyUI answers, which checkpoint it would use, where the
output folder is, and which Aster files it found.

## Wiring Aster's chat backend

The render half needs no setup, and usually the chat half doesn't either.

**Discovery.** On startup the app fetches Aster's own web UI —
`http://127.0.0.1:8787` by default, `asterUrl` or `--aster` to change it — reads
the calls its front end makes, and wires itself to the chat-looking one. It only
*reads*; it never POSTs to an endpoint while probing, since guessing at unknown
routes could trip something with side effects. `--probe` lists everything it
found and which one it picked:

```
aster web UI: http://127.0.0.1:8787
  answered   : yes  - Aster
  calls its page makes (best guess first):
    [fetch] http://127.0.0.1:8787/api/chat
    [fetch] http://127.0.0.1:8787/api/health
  chat endpoint: http://127.0.0.1:8787/api/chat
```

Discovery follows same-origin `<script src>` bundles too, so an endpoint that
only appears in `app.js` is still found. If it picks wrong, or Aster streams over
SSE/WebSocket (which this backend can't speak yet — it says so rather than
mis-wiring), set `http.url` explicitly and discovery is skipped.

The three backends, in the order `auto` tries them:

| backend | when | set |
|---|---|---|
| `http` | Aster listens on a port | `http.url`, or let discovery find it |
| `cli`  | Aster is a command you run | `cli.command` |
| `echo` | nothing wired up yet | — (the fallback) |

Copy `aster.config.example.json` to `aster.config.json` and edit. Both real
backends get the system prompt, the conversation so far, and the new message;
both just need to hand back text.

- **`http`** — `style: "openai"` posts `{model, messages:[…]}` and reads
  `choices[0].message.content`, so anything OpenAI-shaped works as-is.
  `style: "simple"` posts `{message, system, history}` and accepts a reply under
  `reply`, `text`, `content`, or `response` (or plain text). `auto` picks by URL.
- **`cli`** — the composed prompt goes in on **stdin**, the reply is read off
  **stdout**. With `command: null` it auto-detects the Claude Code CLI and runs
  `claude -p`. Deliberately no auto-approve flag: a phone-driven agent with
  blanket tool permissions on the home PC isn't a sane default. Renders don't
  need it — they go through this server's own ComfyUI client, not Aster's tools.
- **`echo`** — the built-in stub, so you can test the phone side before Aster
  exists. The status line reads `chat: echo` when you're on it.

Aster's persona comes from `systemPrompt`. If an Aster `*.md` design sheet turns
up in `ComfyUI-Shared\training\` or `characters\`, it's appended as context
automatically; `--probe` says which file it used.

## Renders

ComfyUI on port **8000** (`comfy.url` to change it). Out of the box it builds the
stock SDXL text-to-image graph, picking an anime/illustration checkpoint if one is
installed. Images save under `<output>/aster/`, so the Gallery tab's **Aster**
toggle shows just these.

For Flux, a LoRA, or img2img, point `comfy.workflow` at an API-format workflow
JSON and use the placeholders `%positive%`, `%negative%`, `%seed%`, `%steps%`,
`%cfg%`, `%width%`, `%height%`, `%model%`, `%prefix%`. A placeholder that's the
whole value keeps its type, so `"steps": "%steps%"` stays an integer.

An Aster `*.txt` prompt file, if found, is prepended to every render prompt; a
`*negative*.txt` becomes the default negative. Override both in the config.

### Renders Aster asks for

When ComfyUI is reachable, Aster's system prompt gains a short protocol: end a
reply with a fenced block and the app queues it, strips the block from what you
see, and drops the image into the chat bubble.

````
```render
{"prompt": "aster, moonlit garden", "aspect": "portrait"}
```
````

`[[render: a close-up]]` works too, a bare prompt inside the fence works, and
`aspect` / `negative` / `steps` / `cfg` / `seed` are all optional. Two per reply
max, so a confused model can't flood the queue.

## Autostart (do this once, then forget it)

```
powershell -ExecutionPolicy Bypass -File install-autostart.ps1
```

Registers a logon task, windowless, picking a Python that can import Pillow so
the phone gets thumbnails. It runs `--probe` first and prints the result, opens
the firewall port if the shell is elevated, then confirms the server answers
before printing the URL to open on the phone.

- `-Port 8778`, `-OutputDir <path>`, `-Python <path to python.exe>` to override
- `-NoToken` to serve with no auth, `-Uninstall` to remove task and firewall rule
- Logs to `aster.log` next to the script — check there first if the icon opens to
  nothing, since a windowless task has nowhere else to complain

## Pin it to the home screen

Open the printed Tailscale URL on the phone, then:

- **iOS / Safari** — Share → Add to Home Screen
- **Android / Chrome** — ⋮ → Add to Home screen / Install app

You get an aster-bloom icon and it opens fullscreen, without browser chrome.

## Access control

Unlike the read-only render gallery, this app talks to Aster and spends GPU time,
so it asks for a token by default. One is generated into `aster.token` on first
run and the startup URL carries it as `?t=…`; opening that link once sets a
cookie, so you don't paste it again on that phone. `--no-token` turns it off.

Still plain HTTP with no TLS — **keep it on Tailscale.** Don't point ngrok or a
Cloudflare tunnel at this port. Path traversal outside the output folder is
refused, and a request that misses locally is only retried through ComfyUI's own
`/view`, never as a raw path.

## Notes

- The transcript lives in `aster-chat.json` next to the script, so reopening the
  app on the phone doesn't lose the thread. Delete it to start clean.
- Job cards poll every 3s while anything is queued or running, and the Gallery
  reads the output folder directly — so renders you started in ComfyUI's own UI
  show up there too.
- Tapping any image gives the full view plus the settings pulled out of the PNG:
  model, seed, steps, cfg, sampler, size, prompt.
- `aster.config.json`, `aster.token`, `aster-chat.json` and `aster.log` are
  gitignored — this repo is public.
