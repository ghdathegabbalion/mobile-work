# Kaarten — practice renders on the PC (SSH session)

Everything needed is in this folder. Rendering only works from an **SSH session** (Termius → PC over Tailscale) — the web/mobile sandbox has no GPU and no local ComfyUI.

## Start

```
cd C:\Users\GH-DA\mobile-work
git pull
C:\Users\GH-DA\claude-remote.cmd
```

Then paste:

> Read `characters/RUN-ON-PC.md` and do the img2img practice batch off `characters/ref/kaarten-ref.png`.

## Preflight (Claude does this first)

1. Confirm ComfyUI is up — GET `http://127.0.0.1:8000/system_stats`. If it's down, start it before anything else.
2. `list_models` — the settings below branch on what's actually installed. Pick in this order:
   - an **anime/illustration SDXL** checkpoint (Pony, Illustrious, NoobAI, Animagine) — best fit for this character
   - else **Flux dev**
   - else whatever SDXL base exists
3. Reference sheet: `characters/ref/kaarten-ref.png` (1128×1408, portrait).

## The practice batch

Four variations, same seed family, so results are comparable. Save into
`C:\Users\GH-DA\ComfyUI-Shared\output\kaarten\` (do **not** commit outputs to this repo).

| # | Mode | denoise | Purpose |
|---|------|---------|---------|
| 1 | img2img off the ref | 0.35 | Sanity check — should look near-identical. Confirms the model can hold the costume. |
| 2 | img2img off the ref | 0.55 | The useful one. Same design, fresh rendering. |
| 3 | img2img off the ref | 0.75 | Loose — expect costume drift; shows where the prompt is too weak. |
| 4 | text-to-image, no ref | — | Baseline, to see how much the ref is actually doing. |

Settings by family (start here, adjust from results):

- **SDXL / Pony / Illustrious:** 1024×1280 (or 832×1216), 28–32 steps, CFG 6–7, `dpmpp_2m` + `karras`.
- **Flux dev:** 1024×1280, 20–25 steps, guidance 3.5, `euler` + `simple`. No negative prompt — Flux ignores it.

Positive prompt: `characters/kaarten-prompt.txt`
Negative prompt (SDXL only): `characters/kaarten-negative.txt`
Full design spec, if the prompt needs rebuilding: `characters/kaarten.md`

## What to report back

For each of the four: which traits held and which drifted — specifically the **striped pantaloons**, **orb staff**, **emerald heart gem**, **rainbow hair gradient**, and **red wings**. That tells us whether the next step is prompt weighting or a small LoRA trained off the ref.

## Known-good from the cloud run

Comfy Cloud / `bfl/flux-2-pro`, seed 77420 held everything except portrait framing. Local results should beat that, since local can use the ref image directly.
