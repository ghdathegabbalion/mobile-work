# Aster — render her on the PC (SSH session)

Rendering Aster only works from an **SSH session** on the PC. The web/mobile sandbox has no
GPU and no local ComfyUI, and cloud text-to-image has been tried and does not work for her
(see the evidence table in `aster.md`).

This is **free** — it runs on the PC's own GPU, not a paid API.

## Start

```
cd C:\Users\GH-DA\mobile-work
git pull
C:\Users\GH-DA\claude-remote.cmd
```

Then paste:

> Read `docs/aster-render-on-pc.md` and render Aster's canonical reference.

## Preflight

1. ComfyUI up? `GET http://127.0.0.1:8000/system_stats`. Start it if not.
2. Her LoRA present? `Documents\ComfyUI\models\loras\aster-illustrious-v1.safetensors`
   If it's missing she is still training and none of this will hold her.
3. Base checkpoint present? `furrytoonmix_xlIllustriousV2.safetensors`
4. Her sprites, for img2img input:
   `ghdathegabbalion/Aster` → `sprites/` (`wave.png` and `shy.png` are the best full-body;
   `idle_cut.png` is the chibi/desktop form and the clearest view of the **moon pouch**).

## Settings

| | |
|---|---|
| Trigger word | `asterfen` — must be first in the prompt |
| LoRA strength | 0.8 model / 0.8 clip (her server's working value) |
| Size | 832×1216 portrait, or 640×832 for chibi |
| Steps / CFG | 28–32 / 6–7 |
| Sampler | `dpmpp_2m` + `karras` |

Positive: `characters/aster-prompt.txt`
Negative: `characters/aster-negative.txt`
Ready-made graph: `characters/aster-workflow.json`
Full spec: `characters/aster.md`

## The batch

Save into `C:\Users\GH-DA\ComfyUI-Shared\output\aster\` — do **not** commit outputs here.
Only the one chosen reference gets committed, as `characters/ref/aster-ref.png`.

| # | Mode | denoise | Purpose |
|---|---|---|---|
| 1 | txt2img, LoRA only | — | Baseline. Shows what the LoRA holds unaided. |
| 2 | img2img off `wave.png` | 0.45 | Expected best. Her style and pose preserved, cleaned up. |
| 3 | img2img off `wave.png` | 0.65 | Looser — new pose, design should still hold. |
| 4 | txt2img + `chibi, super deformed` | — | The desktop-pet form, for a matching chibi reference. |

For the canonical reference specifically, aim for: **full body, head to feet, front-facing,
neutral standing pose, plain or very simple background.** The point is legibility, not scenery.

## What to check in every output

Score each against the locked traits in `aster.md`. The first one is the one that keeps failing:

1. **Exactly one tail** — cream fur at the base, marigold band, ink-violet tentacle at the
   tip, all on **one continuous limb**. Two separate appendages is a failure, no matter how
   pretty. This is the single most common defect.
2. **Blonde bob with bangs** actually visible, not merged into head fur.
3. **The moon pouch** — brown leather, gold crescent.
4. **Ink-dipped paws** as a soft gradient, not gloves.
5. Ears, chevron, freckles, amber eyes.

## Then

Commit the winner as `characters/ref/aster-ref.png`, note in `aster.md` which mode and
denoise produced it, and point the aster-app at the graph so every future render is
conditioned:

```json
"comfy": { "workflow": "C:\\Users\\GH-DA\\mobile-work\\characters\\aster-workflow.json" }
```

`characters/aster-prompt.txt` and `aster-negative.txt` are picked up automatically by
`find_character_files()` in `tools/aster-app/server.py` once they exist — which, as of this
commit, they do. Confirm with `python server.py --probe`.

## Owed work — regenerating the sprite set

As of 2026-08-08 her sheet carries four traits her twelve sprites **do not have**: the
**marigold band** at the tail transition (the old sprites use coral/pink), the **aster bloom**
at her left ear, **amber** eyes rather than brown, and **ink-dipped paws** as a consistent
rule rather than appearing in one sprite of four. Until the sprites are regenerated, her
deployed art and her sheet disagree — and the sheet wins.

This is a PC job. It needs her LoRA, and the desktop cutouts need an alpha channel that no
cloud image editor will preserve.

### Full form — the eight emotes

`idle, wave, happy, dance, think, sleepy, excited, shy` in `ghdathegabbalion/Aster/sprites/`.

Regenerate each as **img2img off the existing sprite at denoise ~0.45**, not from scratch.
Low denoise keeps her pose, composition and background while letting the palette move. Going
higher re-rolls the whole image and you lose the thing that makes the set coherent.

Keep `characters/aster-prompt.txt` as the positive for every one, appending that sprite's own
outfit and setting — the wardrobe varies by design and should not be flattened.

### Chibi form — the desktop cutouts

`*_cut.png` are **transparent-background cutouts** driving the desktop pet window. This is the
part that needs care:

1. Regenerate the chibi on a **flat pastel background**, not a transparent one — samplers do
   not produce clean alpha.
2. Re-cut it with **`cutout.ps1`** in her repo, which is what produced the existing cutouts.
3. Verify the result actually has an alpha channel before committing. A cutout that lost its
   transparency renders as a **white box** on the desktop, which is an obvious and ugly
   regression.

`aster_pet.py` reads these by filename, so keep the names exactly as they are.

### Check every regenerated sprite against

1. **Exactly one tail**, cream → marigold → ink-violet on one continuous limb. Still the
   most common defect.
2. **The marigold band** actually present, replacing the old coral.
3. **The aster bloom** at the left ear, violet petals and gold centre, small.
4. **The moon pouch**, brown leather with the gold crescent.
5. **Amber eyes**, not brown.
6. **Ink-dipped paws** as a soft gradient, not gloves.

When the set is done, update `characters/aster.md` to delete the *Debt this creates* section —
that section existing is the marker that this job is outstanding.
