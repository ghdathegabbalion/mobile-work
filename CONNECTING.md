# Connecting from your phone

Two ways to drive Claude Code in this repo from mobile.

## 1. SSH into the PC — full power (GPU, ComfyUI, local files) · WORKING

Already set up: OpenSSH Server (port 22, **key auth**) + Tailscale. Use the **Termius** app (in-app key gen; Termux was painful and is not recommended).

- **Host:** the PC's Tailscale **100.x IP** — mobile clients can't resolve the MagicDNS name, so dial the IP. (Actual address is in your private setup notes — intentionally not committed to this public repo.)
- **Port:** `22` · **User:** `GH-DA` · **Auth:** your ED25519 key. (Password auth is a dead end from a phone keyboard — key only.)
- After connecting:

  ```
  cd C:\Users\GH-DA\mobile-work
  C:\Users\GH-DA\claude-remote.cmd
  ```

  Save `claude-remote.cmd` as a Termius **Snippet** (or run-on-connect) for one-tap launch. It starts the desktop CLI from the physical MSIX path — SSH sessions don't follow the `%APPDATA%\Claude` redirect. The `bin\claude.cmd` shim now handles that path too, so plain `claude` also works.

## 2. Claude Code web / mobile app — text work (no GPU)

Once this repo is on GitHub:

- Open it in Claude Code on the web/mobile app (claude.ai/code).
- Edit code, docs, notes, and workflow JSONs in a cloud sandbox.
- **Rendering / ComfyUI is not available here** — that's SSH-only.

## Keep them in sync

`git pull` at the start of a session; commit and push often so phone, cloud, and PC never drift apart.
