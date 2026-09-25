# Sprite regen — bring Aster's sprites up to canon

Her 13 sprites (8 full emotes + 5 chibi desktop-pet cutouts in `ghdathegabbalion/Aster/sprites/`)
predate her current design. This kit re-renders every one **img2img off itself**, so pose,
outfit and setting survive while the design moves to canon. It's the owed work that
`../aster.md` → *Debt this creates* tracks.

**PC only** (SSH or the desktop): it needs local ComfyUI on port 8000 and her LoRA. It
doesn't work in the cloud sandbox.

## Run

```
cd C:\Users\GH-DA\mobile-work
git pull
python characters\sprite-regen\regen.py --dry-run          # see the plan, touches nothing
python characters\sprite-regen\regen.py --sprites C:\Users\GH-DA\Aster\sprites
```

It checks ComfyUI, the checkpoint and the LoRA are there before queuing anything. The full
run is **52 renders**: 13 sprites × 2 denoise strengths × 2 seeds. Handy flags:

| flag | does |
|---|---|
| `--only happy dance` | just those sprites |
| `--seeds 4` | more candidates per strength |
| `--denoise 0.5` | one strength for everything, overriding `sprites.json` |

Output goes to ComfyUI's output folder under `aster/regen-<date-time>/`, named
`<sprite>_d<denoise>_s<seed>`. The aster-app Gallery tab shows it, so you can pick from
the phone. **Nothing is overwritten**, in this repo or in hers.

Tuning lives in `sprites.json`: per-sprite scene text, denoise, and a `fix` note saying
what's wrong with the current file.

## Animation frames (`--frames`)

The desktop pet now plays multi-frame animations: wave, dance, celebrate, spin and 14
more, 68 frames in all. Until real frames exist it fakes them from the stills.
`--frames` renders them, each img2img off `idle_cut.png` at high denoise, so the pose
changes while scale, baseline and palette stay put. All frames of one clip share a seed.

```
python characters\sprite-regen\regen.py --sprites C:\Users\GH-DA\Aster\sprites --frames --priority 1
```

| flag | does |
|---|---|
| `--priority 1` | the 21 most visible frames (wave, happy, dance, celebrate). `2`–`4` add more |
| `--only dance spin` | just those clips |
| `--seeds 3` | three candidate looks per clip; pick the seed whose frames match best |

Output is named `<clip>_NN_cut_d<denoise>_s<seed>`. Cut each winner with `cutout.ps1`
to `Aster\sprites\<clip>_NN_cut.png` and restart the pet. It picks them up with no code
change. Names, counts and timing come from `docs/pet-frames.md` in her repo, which is
the source of truth. Keep `sprites.json` → `frames` in step with it.

**Paint the tail in the idle position** (low, to her right). The pet strips each
frame's tail and animates one shared tail, so a tail anywhere else leaves a seam.

## Pick winners

Open each sprite's candidates and score them against this list. Go in order: a render
that fails #1 is out, however pretty it is.

1. **Exactly one tail.** Cream fur → marigold band → ink-violet tentacle on one continuous
   limb. Still the most common defect. `happy` is the worst offender and gets higher denoise
   for that reason.
2. **Marigold band** at the transition, not the old coral.
3. **Aster bloom** at the left ear: small, violet petals, gold centre.
4. **Moon pouch**: brown leather, gold crescent. Canon in **every outfit**, pyjamas included.
5. **Amber eyes**, not brown.
6. **Ink-dipped paws**, a soft gradient on hands and feet, not gloves. **Required** on
   every sprite.
7. **Blonde bob with bangs** actually visible.
8. **Lavender** on every sweater. It's her locked colour. Non-sweater outfits vary freely.

**Denoise tradeoff.** Lower denoise (0.45) keeps the picture but may not add the new traits
(pouch, bloom). Higher (0.55+) adds them but re-rolls more of the image. If a candidate
gets everything right except one thing, **inpaint that one thing, don't re-roll**. That's
the rule from `../aster.md`.

**The two wave frames are a pair.** The pet animates between `wave_02_cut` and `wave_03_cut`,
so pick both at the **same denoise and seed**. They're planned with matching seeds so
that's possible.

## Install winners into her repo

Full sprites: copy to `Aster\sprites\<name>.png`, same filename.

Chibi cutouts render on flat mint, so they need keying first:

```
powershell -File C:\Users\GH-DA\Aster\cutout.ps1 <winner.png> C:\Users\GH-DA\Aster\sprites\<name>.png
```

Then **check each cutout really has transparency** before committing. One that lost its
alpha channel shows up as a mint box on the desktop. `aster_pet.py` loads by filename, so
keep the names exactly: `idle_cut`, `think_cut`, `sleepy_cut`, `wave_02_cut`, `wave_03_cut`.

When all 13 are in, delete the *Debt this creates* section from `../aster.md`. That section
existing is the marker that this job is still outstanding.

## Tests

```
python -m unittest characters/sprite-regen/test_regen.py
```

These run against a fake ComfyUI, with no GPU, so they also pass in the cloud.
