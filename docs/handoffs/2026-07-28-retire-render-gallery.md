# Retiring render-gallery: one step left, and it's on the PC

**From:** Claude · **Date:** 2026-07-28 · **Branch:** claude/aster-mobile-app-nkxb40

## What I was doing

`tools/mobile-work` had two phone apps served from the PC over Tailscale:
`tools/render-gallery/` (a read-only grid of ComfyUI's output folder, port 8777)
and `tools/aster-app/` (chat with Aster + queue renders + the same grid, port
8778). The owner asked to combine them into one app.

The Aster app's Gallery tab was already a feature superset, so I gave that app a
second home-screen entry point (`/gallery`, gold star icon, opens on the grid)
and deleted `tools/render-gallery/`.

## State

Done and committed:

- `tools/render-gallery/` deleted.
- `tools/aster-app/` serves two installable tiles from one process: `/` (Chat,
  aster bloom) and `/gallery` (Gallery, gold star). The star is byte-identical to
  the deleted tool's icon — verified by hashing both — so the pinned tile looks
  unchanged.
- `CLAUDE.md` updated so nobody recreates the old tool.
- Verified in a headless browser: both entry points land on the right tab with
  the right manifest, the auth cookie carries between them, and the full app
  regression passes.

**Not done, and cannot be done from a cloud sandbox:** the PC still has a
scheduled task named **ComfyUI Render Gallery** that launches
`tools\render-gallery\server.py` at logon, plus a firewall rule holding TCP
**8777** open. That path no longer exists, so the task now fails silently at
every logon.

## Open questions

None about the design. The only uncertainty is whether the owner has already run
the uninstall on the PC — there's no way to tell from the repo. Check for the
task before assuming it's still there.

## Next step

On the PC, in an admin PowerShell, remove the stale task and firewall rule. The
script that used to do this (`install-autostart.ps1 -Uninstall`) was deleted with
the folder, so don't go looking for it — these two lines are the whole job:

```powershell
Unregister-ScheduledTask -TaskName 'ComfyUI Render Gallery' -Confirm:$false
Get-NetFirewallRule -DisplayName 'ComfyUI Render Gallery' | Remove-NetFirewallRule
```

Check first whether the task is even still there — the owner may have already
done it:

```powershell
Get-ScheduledTask -TaskName 'ComfyUI Render Gallery' -ErrorAction SilentlyContinue
```

Then re-pin `http://<tailscale-ip>:8778/gallery` on the phone and delete the old
8777 icon. **Delete this handoff note once that's done.**
