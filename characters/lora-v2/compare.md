# v1 vs v2: how to compare and score

The question this answers: **does `aster-illustrious-v2` hold her current canon better than
v1, without losing her look?** It is a fixed grid: same prompts (`eval_prompts.txt`), same
seeds, same size, steps, CFG and LoRA strength (0.8). The LoRA is the only thing that changes.

## Run it (PC)

```
cd C:\Users\GH-DA\mobile-work\characters\lora-v2
python compare.py --dry-run                     # plan: 12 prompts x 3 seeds x 2 LoRAs = 72 renders
python compare.py                               # v1 vs final v2
```

Pick the epoch first. Every 2 epochs is saved; compare the later ones on the hardest prompts:

```
python compare.py --only back_tail face paws_sit chibi --loras e6=aster-illustrious-v2-000006.safetensors e8=aster-illustrious-v2-000008.safetensors e10=aster-illustrious-v2-000010.safetensors v2=aster-illustrious-v2.safetensors
```

Then run the full grid with the winner against v1: `--loras v1=aster-illustrious-v1.safetensors v2=<winner>`.
A control column is `none=none` (the bare checkpoint). If v2 "wins" by less than v1 beats
the control, the LoRA isn't doing much.

Output: `%USERPROFILE%\lora-v2\compare\compare-<stamp>.html` (the grid, one row per
prompt and seed, one column per LoRA) and `scores-<stamp>.csv` (blank, one row per image).

## Score each image

Fill the CSV with `1` (pass), `0` (fail) or blank (not in frame). The columns are the
canon checklist from `canon_tags.json`, the same one `curate.py` uses:

| column | pass means | watch for |
|---|---|---|
| `one_tail` | exactly one tail: cream fur, marigold band, ink-violet tentacle, **one continuous limb** | a fox tail plus a separate tentacle; two tentacles; no tail. **Scored first; a fail here is a fail for the image** |
| `marigold_band` | a warm marigold/amber band where fur becomes tentacle | the old coral/pink; no band at all |
| `aster_bloom` | small aster at the base of the **left** ear, violet petals, gold centre | wrong ear; a generic flower; too big |
| `moon_pouch` | brown leather hip pouch, gold crescent on the flap | missing with sundress/pyjamas (it's in every outfit) |
| `amber_eyes` | warm amber-gold | brown |
| `ink_paws` | cream fading softly to violet at wrists and ankles, mauve pads | hard-edged gloves or socks; plain cream paws |
| `blonde_bob` | blonde bob with blunt bangs, visibly hair | merged into head fur |
| `lavender_sweater` | any sweater is lavender (blank if no sweater) | white or grey sweater. `sweater` prompt names no colour on purpose |

Also note in `notes`: **style drift** (does it still look like her `wave.png` /
`aster-ref-style.png`?), orange fur, extra limbs, and whether `bare` prompts look like her
at all.

## Read the result

Per LoRA, per column: passes / scored images. Two readings matter most:

1. **`bare` rows, trigger only.** This is what v2 is for. v1 needs the whole canon prompt and
   still misses the band, bloom, eyes and paws. A good v2 gets most of them from `asterfen`
   alone.
2. **`one_tail` on `back_tail`, `side_walk`, `canon_back`.** The load-bearing trait, in the
   angles v1 was never trained on.

Ship v2 (copy it into `Documents\ComfyUI\models\loras\` for everyday use) when:

- `one_tail` pass rate is **at least v1's** on every angle, and higher overall;
- it is higher than v1 on at least 4 of `marigold_band`, `aster_bloom`, `moon_pouch`,
  `amber_eyes`, `ink_paws`, `lavender_sweater`;
- the `notes` show no loss of her style. A v2 that is more correct but no longer looks like
  her art is not a win: the design file and the style file both have to hold.

That decision is Kaarten's. Two models agreeing that v2 is better is not evidence.

## If v2 fails one trait

Don't retrain from scratch. Find the trait in the dataset: too few images show it
(`paws_closeup`, `tail_closeup`), or some kept image shows it wrong. Fix the dataset, not
the hyperparameters. Overfitting (every image the same pose, background bleeding through)
means pick an earlier epoch.
