# mobile-work

A lightweight workspace for driving Claude Code from a phone — either over **SSH into the home PC** (full power) or from the **Claude Code web/mobile app via GitHub** (text-only, no GPU).

## What this repo is for

General on-the-go work: code, writing/docs, art-pipeline control, and scratch. Structure is intentionally minimal — grow it organically. Do not copy models or large binaries in here; reference the main workspace instead.

## Two ways in — and what each can actually do

- **SSH into the PC (over Tailscale)** — runs on the real machine. Full access: local files, the `comfyui` MCP tools, the GPU, and the main workspace at `C:\Users\GH-DA\ComfyUI-Shared`. Use this for anything that renders or touches models.
- **Claude Code web/mobile app (via GitHub)** — runs in a cloud sandbox. Text work only: edit code, docs, notes, workflow JSONs. **No GPU, no ComfyUI, no access to the PC's files.** Don't attempt to render here.

**Know where you are:** if the `comfyui` MCP tools and `C:\Users\GH-DA\ComfyUI-Shared` are reachable, you're on the PC (SSH) → full power. If not, you're in the cloud sandbox → text only.

## Working conventions

- **Be concise.** Output is read on a small screen — lead with the answer, keep it short, avoid long dumps.
- **Commit and push often.** This repo syncs across phone / cloud / PC; frequent small commits keep the three aligned and avoid conflicts. `git pull` at the start of a session.

## Art pipeline (SSH sessions only)

The real art workspace lives at `C:\Users\GH-DA\ComfyUI-Shared`:

- Workflows: `ComfyUI-Shared\workflows\*.json`
- Character / design recipes: `ComfyUI-Shared\training\` (e.g. the Aster design sheet)
- Prefer the `comfyui` MCP tools (`generate_image`, `img2img`, `inpaint`, `upscale_image`, `list_models`). ComfyUI runs on **port 8000** — verify it's up (GET /system_stats) before assuming.

## Phone-facing tools (they run on the PC, you reach them from the phone)

Both are stdlib-only Python servers, pinned to the phone home screen over Tailscale:

- `tools/aster-app/` — chat with Aster + queue renders + gallery. Aster's chat backend is pluggable; `python server.py --probe` reports what it actually resolved. Read its README before changing it.
- `tools/render-gallery/` — read-only grid of ComfyUI's output folder.
