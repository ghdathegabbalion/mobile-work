# Connecting from your phone

Two ways to drive Claude Code in this repo from mobile.

## 1. SSH into the PC — full power (GPU, ComfyUI, local files)

The PC already runs OpenSSH Server and is on your Tailscale tailnet.

From a phone SSH client (e.g. Termux, or a Tailscale-aware terminal), **with your phone on the same tailnet**:

```
ssh GH-DA@<your-tailnet-name>
cd mobile-work
claude
```

- Host is your Tailscale **MagicDNS name** or **100.x IP**; user is the Windows account `GH-DA`.
  (Actual address is in your private setup notes — intentionally not committed to this public repo.)
- `claude` runs through the shim at `C:\Users\GH-DA\bin\claude.cmd`, which resolves the desktop CLI from the physical Packages path (works from an SSH shell, which lives outside the app's MSIX container).
- First CLI login on a fresh shell may prompt for `/login` once.

## 2. Claude Code web / mobile app — text work (no GPU)

Once this repo is on GitHub:

- Open it in Claude Code on the web/mobile app (claude.ai/code).
- Edit code, docs, notes, and workflow JSONs in a cloud sandbox.
- **Rendering / ComfyUI is not available here** — that's SSH-only.

## Keep them in sync

`git pull` at the start of a session; commit and push often so phone, cloud, and PC never drift apart.
