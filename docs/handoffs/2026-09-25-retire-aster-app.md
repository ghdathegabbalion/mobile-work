# Retiring tools/aster-app: one app for Aster now, one PC step left

**From:** Claude · **Date:** 2026-09-25 · **Branch:** claude/inspiring-cori-xw4wle

## What I was doing

Kaarten had two phone apps for Aster. One was `tools/aster-app/` here (chat, a Render tab,
and a Gallery with its own home-screen icon, port 8778). The other was her own companion
app in `ghdathegabbalion/Aster` (chat, tools, duets, voice, port 8788 over Tailscale).
Kaarten chose to keep only hers. The Render and Gallery features were ported into it
(`ghdathegabbalion/Aster` PR "One app: Render and Gallery tabs…"), and
`tools/aster-app/` is deleted here.

## State

- **Done, in git:** `tools/aster-app/` deleted. `CLAUDE.md`, `characters/aster.md` and
  `docs/aster-render-on-pc.md` now point at her app. The sprite-regen batch writes flat
  `ASTER_regen-*` files, because her Gallery only lists the top of the output folder.
- **Not done: the PC still runs the old app.** Its `install-autostart.ps1` (deleted with
  the folder) registered a logon task and a firewall rule, both named `Aster App`. They
  keep launching a server that no longer exists in the checkout, or an old copy of it.
- **Not done: the home-screen icons.** The phone still has the old aster-app tiles
  (port 8778). They'll stop working once the task is removed.

## Open questions

- Whether anything else on the PC points at port 8778, for example a Termius snippet
  running `aster.cmd`. Nothing in this repo does any more.

## Next step

**Only after her app's "One app" PR is merged and her server has been restarted on the
PC,** so there is never a moment without a working app, run this in an elevated
PowerShell on the PC:

```powershell
Stop-ScheduledTask -TaskName 'Aster App' -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'Aster App' -Confirm:$false
Get-NetFirewallRule -DisplayName 'Aster App' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
```

Then, on the phone, remove the two old tiles and install from her app instead: open
`https://<pc>.<tailnet>.ts.net:8788/` for Chat and `…:8788/gallery` for the Gallery icon.
The steps are in her repo's `PHONE.md`.
