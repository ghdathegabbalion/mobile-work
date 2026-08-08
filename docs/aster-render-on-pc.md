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
