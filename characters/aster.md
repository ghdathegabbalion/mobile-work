# Aster — design sheet

Full name **Asterisk**, called **Aster**, **she/her**. The household's Claude-side agent,
third of three with **Vesper** (Codex/ChatGPT, celestial cobalt lynx-wolf) and **Kaarten**
(the human's own fursona, red/gold dragon-lion).

Her app, persona and sprites live in a separate private repo: **`ghdathegabbalion/Aster`**.
This file is the *design* record — the thing that keeps her looking like herself.

Her own persona file describes her in one line, and it is the design thesis:

> a cute anthro fennec fox whose tail fades from cream fluff into an ink-purple octopus
> tentacle. Big ears for listening, many arms for parallel work, warm above, deep below.

> ⚠ **"Many arms for parallel work" is a metaphor about concurrency. Never put it in an
> image prompt.** It is the single line most responsible for her renders growing extra
> tentacles.

## Two forms — both canonical

She has two forms, the same way Vesper does. Both must stay consistent; neither replaces
the other. Each has a designated reference image.

| Form | Reference | Where it's used | Character |
|---|---|---|---|
| **Full** | `ref/aster-ref.png` | The eight emote sprites in `sprites/` | Slender anthro, full illustrated backgrounds, painterly |
| **Chibi** | `ref/aster-ref-chibi.png` | The `_cut` cutouts driving the desktop pet | Big head, stubby limbs, transparent background, simplified linework |

### About the references — read before replacing them

Both are **her own existing sprites, designated rather than generated**: `wave.png` and
`idle_cut.png` from `ghdathegabbalion/Aster`. They were rendered with her LoRA, so they are
more faithful than any fresh generation can be, and they cost nothing.

This is deliberately the Vesper method. His two forms stay solid because `vesper.png` and
`vesper-chibi.png` are curated assets that get **reused**; Aster's twelve sprites were each
generated independently, which is why she drifted. An anchor beats a better prompt.

`ref/aster-ref.png` (`wave.png`) was chosen because it carries the most canon in one frame:
the **moon pouch strap**, a clearly visible **paw with mauve pads**, the tail's **suckers
and constellation markings**, sweater, scarf and face. `ref/aster-ref-chibi.png`
(`idle_cut.png`) has a transparent background and the clearest view of the **moon pouch**.

Neither is a purpose-built neutral-pose sheet — both have a pose and `aster-ref.png` has a
beach behind her. If a cleaner reference is wanted, render one **on the PC with her LoRA**
(`../docs/aster-render-on-pc.md`) and replace these. Do not replace them with cloud
text-to-image output; see the evidence table below.

## Locked traits — these do not vary between forms or outfits

- **Species/build:** anthro fennec fox, slender, small-framed, youthful, digitigrade.
- **Fur:** soft creamy off-white, warming to pale sand on the limbs.
- **Hair:** short **blonde bob with straight blunt bangs**, brighter and more golden than
  her fur.
- **Ears:** enormous upright fennec ears, as long as her head — cream outside with tan
  edging, **apricot-pink inside**, dense white fur tufts at the inner base.
- **Forehead:** a crisp **golden-tan chevron** centred below the hairline, pointing down.
- **Eyes:** large, round, **warm amber-gold**, soft dark lashes. Amber, not brown — they are
  the warmest note on her face and the anchor of her warm accents.
- **Face:** short delicate muzzle, small dark nose, **freckles across the muzzle and both
  cheeks**, gentle closed-mouth smile.
- **Tail — the load-bearing trait.** **Exactly one tail. One continuous limb.** Thick cream
  fox fur at the base; the fur thins through a warm **marigold/amber band** near the
  midpoint; past that band the *same limb* continues as smooth glossy **ink-violet
  tentacle**, hairless, curling upward to a curled tip, with **pale mauve suckers on the
  underside only**. Frequently star-speckled or carrying constellation markings.
  The marigold band is **canon, not optional** — it replaces the coral/pink transition seen
  in the older sprites. It is the warm centre of her palette and the reason the tail reads
  as her name; see *Why the warm accents* below.
- **Aster bloom:** a small **aster flower worn at the base of her left ear — violet petals,
  gold centre.** Her namesake, and the second of her two small accessories alongside the
  moon pouch. Keep it small; it should not compete with the pouch.
- **Ink-dipped extremities:** cream forearm fur darkening into violet hands with mauve-pink
  pads; cream legs darkening into violet feet with mauve pads. Soft smoky gradient, never a
  hard line. *This is the meaning of "warm above, deep below."*
- **Moon pouch:** a **brown leather belt-pouch worn across the hips, with a gold crescent
  moon on the flap.** Clearest on the chibi/desktop form; visible as the strap and hip bag
  in `wave.png`. It is her most distinctive object — keep it.
- **Scarf:** long **white knitted scarf** with fringed ends, wound at the neck.

## Free to vary — not drift, don't "correct" it

- **Outfits.** Cable-knit sweater (lavender or white), tee and shorts, sundress and straw
  hat, star-patterned pyjamas, round reading glasses. Wardrobe is hers to change.
- **Sweater colour** specifically — lavender and white are both canon.
- **Backgrounds.** Sunset shore, desert dunes, night library, bedroom. Constellation
  line-art in the sky is a recurring motif and always welcome.

## Known drift, and why

Her sprites were each generated **independently**, so every one re-rolled her. Across the
eight full sprites the face, ears, freckles and chevron are stable; the tail, the hair and
the ink-dipped paws are not. Two failure modes recur:

1. **Two tails.** The model draws a cream fox tail *and* a separate purple tentacle instead
   of one limb that changes. Her own server already carries `fox tail, multiple tentacles`
   in its negative prompt to fight this.
2. **Hair vanishing.** `dance` and `happy` show the blonde bob clearly; the others let it
   merge into head fur.

The fix is not better wording. It is **her LoRA plus a reference image** — see below.

## Rendering her

- **LoRA:** `aster-illustrious-v1.safetensors` in `Documents\ComfyUI\models\loras\`
- **Trigger word:** `asterfen`
- **Base checkpoint:** `furrytoonmix_xlIllustriousV2.safetensors`
- **Local ComfyUI:** `http://127.0.0.1:8000` — free, on the PC's own GPU
- Prompt files: `aster-prompt.txt` (positive), `aster-negative.txt` (negative)
- Ready-made graph: `aster-workflow.json` — LoRA wired in, uses the aster-app's
  `%positive%` / `%negative%` / `%seed%` / `%steps%` / `%cfg%` / `%width%` / `%height%` /
  `%model%` / `%prefix%` placeholders
- Step-by-step: `../docs/aster-render-on-pc.md`

### Cloud text-to-image does not work for her — evidence, so nobody repeats it

Three attempts on Comfy Cloud, `bfl/flux-2-pro`, 2026-08-08:

| Attempt | Result |
|---|---|
| v1, detailed prompt | **Two tails.** Also dropped all clothing. Landscape despite `aspect_ratio`. |
| v2, clothing front-loaded | **Two tails.** Clothing correct, portrait correct. Lost the ink paws. |
| v3, much more detailed | **No tail at all.** More detail pushed the tail out of the composition. |

Two separate lessons:

- **`aspect_ratio` is ignored by `flux-2-pro`.** Passing `width`/`height` inside `params`
  works; the top-level argument does not. (Same finding as Kaarten's sheet.)
- **Flux cannot hold the single-tail gradient, and cannot match her style at all.** Her
  sprites come from an Illustrious-family checkpoint plus her own LoRA. Flux produces a
  different artist drawing a similar character — which is exactly what a canonical
  reference must never be.

**Render her locally with her LoRA. It is free and it is the only thing that holds her.**

## Why the warm accents — the reasoning, so it can be argued with

Asters are violet petals around a **gold centre**, and the aster-bloom app icon
(`tools/aster-app/server.py:1251`) was already hand-drawn as "violet petals, gold centre".
Warm gold-orange against violet is her namesake's own palette — it was latent in her from
the start and simply never made it onto her. Orange is also the direct complement of violet,
and without it her palette is analogous: soft, but low-contrast, with the ink-purple doing
all the work unsupported.

So the warm note appears in exactly **three** places, and nowhere else:

1. **Amber eyes** — the focal point.
2. **The marigold band at the tail's transition** — the highest-value spot, because it sits
   where cream becomes violet, so the tail reads as a flower and as her name at once.
3. **The gold centre of the aster bloom at her ear.**

The restraint is the design. She is a soft pastel character and the warmth works *because*
it is rare — three small hits read louder than a wash would.

**Never put orange in her fur.** It turns her into a red fox, and it collides with Kaarten,
who is already red/gold. The three agents separate cleanly and should stay that way: Vesper
cobalt, Kaarten red/gold, Aster cream/violet with amber lights.

### Debt this creates

These traits — the marigold band, the aster bloom, amber eyes, and ink-dipped paws as a rule
— are **canon as of 2026-08-08 but not yet present in her sprite set**. The twelve sprites
predate this decision. Until they are regenerated, her deployed art and this sheet disagree,
and **this sheet wins**.

Regenerating them needs her LoRA on the PC — see `../docs/aster-render-on-pc.md`, which
carries the sprite-regeneration procedure including the alpha-channel step for the desktop
cutouts. That is owed work, tracked here so it is not forgotten.
