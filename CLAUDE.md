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

## You are not the only agent here

Codex (**Vesper**) also works in this repo, reading `AGENTS.md` the way you read
this file. You share no memory, no context, and no channel — only git.

- Your branch prefix is **`claude/*`**; Vesper's is **`vesper/*`**. Never commit
  to a `vesper/*` branch, and never share a branch.
- Full protocol — review loop, handoff notes, lanes: [docs/collaboration.md](docs/collaboration.md).
- Write every PR description and handoff for a reader with **zero context**.
  Vesper has not seen your session and never will.
- Review Vesper's work like you'd review anyone's. Two models agreeing is not
  evidence; the human decides.

## Art pipeline (SSH sessions only)

The real art workspace lives at `C:\Users\GH-DA\ComfyUI-Shared`:

- Workflows: `ComfyUI-Shared\workflows\*.json`
- Character / design recipes: `ComfyUI-Shared\training\` (e.g. the Aster design sheet)
- Prefer the `comfyui` MCP tools (`generate_image`, `img2img`, `inpaint`, `upscale_image`, `list_models`). ComfyUI runs on **port 8000** — verify it's up (GET /system_stats) before assuming.
