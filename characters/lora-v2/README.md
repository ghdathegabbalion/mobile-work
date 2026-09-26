# Aster LoRA v2: dataset, captions, training, comparison

**PC only.** Everything here was written from the cloud sandbox, and nothing here trains or
renders in the cloud. The scripts run on the PC (SSH or desktop) against local ComfyUI
(port 8000) and kohya sd-scripts.

## Why v2

Her LoRA `aster-illustrious-v1.safetensors` (trigger `asterfen`, base
`furrytoonmix_xlIllustriousV2.safetensors`) was trained **before her current canon**. It
never saw the marigold tail band, the aster bloom at her left ear, amber eyes, ink-dipped
paws as a rule, the lavender-sweater rule, the moon pouch in every outfit, or a chibi
carrying the full trait list. So every render has to fight the LoRA for those traits
through the prompt, and the prompt loses about half the time. The canon is in
`../aster.md`; this kit trains a LoRA that has actually seen it.

The plan: **~25–40 curated, canon-correct images → captions from one tag file → one kohya
run → a fixed v1-vs-v2 grid, scored per trait.**

## Files

| file | what |
|---|---|
| `canon_tags.json` | The single source: trigger, locked caption tags (from `aster.md` → Locked traits), the curation checklist, hard exclusions, shot types, the target mix, banned phrases. |
| `curate.py` | Scan candidates → dedupe → `contact_sheet.html` to score → `selection.json` → bucket-sized PNGs in the dataset folder. |
| `caption.py` | One kohya `.txt` caption per image, `asterfen` first. |
| `overrides.json` | Per-image caption overrides (ships with one for `aster-ref`). |
| `train_config/` | `aster-v2.toml` (hyperparameters), `dataset.toml` (template), `sample_prompts.txt`, `train.ps1`. |
| `eval_prompts.txt`, `compare.py`, `compare.md` | The fixed prompt × seed grid, its ComfyUI runner, and the scoring sheet. |
| `test_lora_v2.py` | `python -m unittest characters/lora-v2/test_lora_v2.py`. Stdlib, runs anywhere. |

## 1. What goes in the dataset

### Sources

1. **Regenerated sprites.** `../sprite-regen/` renders all 13 sprites to canon
   (52 candidates) plus the pet's animation frames (`--frames`). These carry her real
   style, poses and outfits. The main source.
2. **`../ref/aster-ref.png`.** The design authority: every locked trait, correct. One image;
   its Comfy Cloud rendering differs from her LoRA look, which is fine as one of ~30.
3. **Best gallery renders** in ComfyUI's output folder (`ASTER_*`), if they pass the checklist.
4. **Chibi frames** from `regen.py --frames`. Many are near-identical (the pet's frames only
   move a paw), which is what the dedupe is for. Cap them.
5. **Gap-fill renders** (step 3 below). Nothing she has shows her **from behind**, and a
   back view is the single best teacher for "one tail". Render them with v1, then curate
   hard.

**Not** `ref/aster-ref-style.png` or `ref/aster-ref-chibi.png`: they are her old palette
(coral band, no bloom). **Not** un-regenerated sprites: every one of them predates the
canon. Scanning `Aster\sprites` is useful only after regen winners are installed there.

### Target mix (in `canon_tags.json` → `mix`; the contact sheet shows it live)

| | target | why |
|---|---|---|
| total | 25–40 | Enough for one character on SDXL; more mostly adds near-duplicates. |
| full form | 18–28 | Her main form. |
| chibi form | 7–12 | Its own form tag; enough that the chibi keeps every trait. |
| full body, front/3-4 | 8–14 | The design read at a glance. |
| **back view** | 4–6 | **The ONE tail**, seen whole, from the root. Her hardest trait. |
| side view | 2–4 | The tail's single limb from another angle. |
| upper body / portrait | 4–6 | Bloom at the left ear, amber eyes, chevron, freckles, bob. |
| tail close-up | 2–3 | Cream fur → marigold band → tentacle, suckers underneath. |
| paws close-up | 2–3 | Ink-dipped hands and feet: soft gradient, not gloves. |
| outfits | ≥ 4, none > 40% | Lavender cable-knit, tee and shorts, sundress, pyjamas, turtleneck... Too many of one outfit and the LoRA thinks the sweater *is* her. Pouch in every one. |
| backgrounds | ≥ 30% simple | Stops her beaches and dunes being learned as part of her. |

### Exclude, always

Hard rejects (a checkbox each on the contact sheet; `curate.py build` refuses them even
if the JSON says keep):

- **two tails**, or a fox tail plus a separate tentacle. Also no tail visible in a shot
  that should show it: in full, back, side and tail shots the tail checks must be *pass*,
  not *n/a*.
- **brown eyes**
- **coral/pink tail band** (old palette)
- **white or grey-white sweater**
- **missing pouch** where it should be in frame
- **orange/red fur**

Every checklist item (one tail, marigold band, bloom, pouch, amber eyes, ink paws, bob,
lavender sweater) must be scored *pass* or *n/a* (not in frame); a *fail* is out. One
wrong image teaches the wrong thing ~200 times over a run, so **when in doubt, leave it
out.** If a render is right except one thing, inpaint that thing and use the fixed one
(the rule from `aster.md`: edit, don't re-roll).

## 2. Captions

`caption.py` writes, for every image:

```
asterfen, [chibi, super deformed], <locked canon tags>, <variable tags>
```

**Locked canon tags** (from `canon_tags.json`, in every caption):

```
anthro, fennec fox, slender, digitigrade, cream fur, blonde bob, blunt bangs,
huge fennec ears, apricot inner ears, golden forehead chevron, amber eyes, freckles,
single tail, fox fur tail base, ink-violet tentacle tail, mauve suckers, marigold tail band,
aster flower at left ear, ink-dipped paws, brown leather hip pouch, gold crescent moon,
white knitted scarf
```

plus `lavender sweater` whenever the image's own tags mention a sweater.

**Variable tags** (outfit, pose, setting, shot) come from, in priority order:
`overrides.json` → what you entered on the contact sheet (shot, outfit, extra tags) → the
scene text in `../sprite-regen/sprites.json` or `eval_prompts.txt`, matched from the
filename (`ASTER_regen-…_<sprite>_d…`, `<clip>_NN_cut`, `ASTER_compare-…_<prompt>_s…`).

**`--shuffle-keep 1`** must equal `keep_tokens = 1` in `train_config/dataset.toml`
(`caption.py --config` checks it). kohya shuffles each caption's comma-separated tags every
step (`shuffle_caption = true`) but never moves the first N. With 1, `asterfen` always leads
and nothing else is positional. 2 would also pin whatever comes second, which is `chibi`
on chibi images but `anthro` on full ones, so 1 is the value.

**Never in a caption:** "many arms for parallel work" or any persona metaphor ("big ears for
listening", "warm above, deep below"), two tails, fox tail, coral, brown eyes. They are in
`canon_tags.json` → `banned_*`; `caption.py` strips them from variable tags and refuses a
caption that still has one. The "many arms" line is the one most responsible for her
growing extra tentacles.

Close-ups: by default every locked tag is in every caption, as specified. `--drop-hidden`
leaves out a trait's tags when you scored it *n/a* (e.g. no tail tags on a face close-up).
Try it only if v2 starts drawing a tail into portraits.

## 3. Step by step on the PC

One-time setup:

```
cd C:\Users\GH-DA\mobile-work
git pull
pip install pillow                                   :: optional; curate.py is 50x faster with it
```

kohya sd-scripts, if not already installed (skip if v1's trainer is still there, and pass
its folder as `-SdScripts`, its python as `-Python`):

```
cd %USERPROFILE%
git clone https://github.com/kohya-ss/sd-scripts
cd sd-scripts
python -m venv venv
venv\Scripts\activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
pip install bitsandbytes
```

Then:

```
:: 1. Canon-correct candidates (needs ComfyUI up on :8000, v1 LoRA installed)
cd C:\Users\GH-DA\mobile-work
python characters\sprite-regen\regen.py --sprites C:\Users\GH-DA\Aster\sprites
python characters\sprite-regen\regen.py --sprites C:\Users\GH-DA\Aster\sprites --frames --priority 1

:: 2. Gap-fill: back/side views, close-ups, other outfits, rendered with v1 (different seeds
::    from the eval grid, so the comparison stays clean)
cd characters\lora-v2
python compare.py --loras v1=aster-illustrious-v1.safetensors --seeds 8 --seed-base 777000 --only back_tail side_walk canon_back face paws_sit sundress pyjamas

:: 3. Contact sheet: score every candidate in the browser, then "Download selection.json"
::    and save it as %USERPROFILE%\lora-v2\work\selection.json
python curate.py sheet --src "%USERPROFILE%\Documents\ComfyUI\output::ASTER_*" --src ..\ref\aster-ref.png --work %USERPROFILE%\lora-v2\work
start %USERPROFILE%\lora-v2\work\contact_sheet.html

:: 4. Dataset: check the mix, then write bucket-sized PNGs
python curate.py build --selection %USERPROFILE%\lora-v2\work\selection.json --dataset %USERPROFILE%\lora-v2\dataset --dry-run
python curate.py build --selection %USERPROFILE%\lora-v2\work\selection.json --dataset %USERPROFILE%\lora-v2\dataset

:: 5. Captions: read a few, then write them
python caption.py --dataset %USERPROFILE%\lora-v2\dataset --config train_config\dataset.toml --dry-run
python caption.py --dataset %USERPROFILE%\lora-v2\dataset --config train_config\dataset.toml

:: 6. Train. Close ComfyUI first (it holds RAM and VRAM)
powershell -ExecutionPolicy Bypass -File train_config\train.ps1 -DryRun
powershell -ExecutionPolicy Bypass -File train_config\train.ps1

:: 7. Compare: copy the checkpoints into ComfyUI's loras folder, start ComfyUI, pick the epoch,
::    then run the full grid and score it (compare.md)
copy %USERPROFILE%\lora-v2\output\aster-illustrious-v2*.safetensors %USERPROFILE%\Documents\ComfyUI\models\loras\
python compare.py --only back_tail face paws_sit chibi --loras e8=aster-illustrious-v2-000008.safetensors e10=aster-illustrious-v2-000010.safetensors v2=aster-illustrious-v2.safetensors
python compare.py --loras v1=aster-illustrious-v1.safetensors v2=aster-illustrious-v2.safetensors
```

If ComfyUI's output folder or the checkpoint lives elsewhere, pass `--comfy-output` to
`compare.py` and `-Checkpoint` to `train.ps1`. The folder paths above are defaults, not
requirements.

When v2 wins (the rule is in `compare.md`, the call is Kaarten's): point `regen.py`'s
`DEFAULT_LORA`, `aster-workflow.json` and `aster.md` → *Rendering her* at v2, and delete v1
only after a week of actually using v2.

## 4. Training defaults, and why

For ~30 images on SDXL/Illustrious, 12–16 GB VRAM, 16 GB system RAM.

| setting | value | why |
|---|---|---|
| `network_dim` / `alpha` | 16 / 8 | One character needs little capacity. 16 holds her fine detail (suckers, bloom) without memorising backgrounds; alpha = dim/2 halves the effective step, a steadier learn at 1e-4. ~90 MB file. |
| `network_train_unet_only` | true | SDXL's two text encoders are easily damaged by a small dataset, and `asterfen` is already a rare token the UNet can bind to. Saves ~2 GB VRAM. |
| optimizer / lr | AdamW8bit, 1e-4, cosine, 100 warmup | The standard SDXL LoRA baseline; 8-bit states save VRAM. No adaptive-LR optimiser, so runs are repeatable and comparable. |
| epochs / repeats | 12 epochs, repeats = round(180 / images) | ~180 steps per epoch whatever the dataset size (30 images → 6 repeats → 2,160 steps). Character LoRAs on SDXL usually land at 1,500–2,500 steps. |
| `save_every_n_epochs` | 2 | Six checkpoints (2 … 12). The best one is often not the last; `compare.py` picks. |
| batch size | 1 | Fits 12 GB. On 16 GB, batch 2 works; halve `-StepsPerEpoch` to keep the same number of image views. |
| resolution / buckets | 1024, SDXL buckets 512–1536, step 64, no upscale | `curate.py` already sized every image to an exact bucket (fit and pad, never crop, so a tail at the frame's edge survives). |
| `shuffle_caption` / `keep_tokens` | true / 1 | Trigger pinned first, every other tag shuffled, so no tag is learned by position. |
| `flip_aug` | **false** | The aster bloom is on her **left** ear. Flipping teaches "either ear". |
| `color_aug` | false | Her palette is the design. |
| `noise_offset` | 0.0357 | Mild. Helps the deep ink-violet and bright cream at once, without shifting overall brightness. |
| `min_snr_gamma` | 5 | Evens out loss across timesteps; faster, steadier convergence on small sets. |
| `max_token_length` | 225 | Her captions are ~90 CLIP tokens. At the default 75 the tail and pouch tags would be cut off. |
| precision | bf16 train, fp16 save, `no_half_vae` | bf16 is stable on RTX 30/40 (`-Fp16` for older cards). The SDXL VAE produces NaNs in half precision. |
| `gradient_checkpointing`, `sdpa` | on | The two biggest VRAM savers; sdpa needs no xformers install. |
| sample prompts | every 2 epochs, 7 prompts | Trigger + scene only, fixed seeds, one per trait: front, **back view**, face (bloom and eyes), paws, sundress (pouch), sweater (colour), chibi. |

### 12–16 GB VRAM, 16 GB RAM

The PC has been RAM-constrained before. Loading the SDXL checkpoint is the peak, near 10 GB
of system RAM, before anything reaches the GPU.

- **Close ComfyUI before training.** It holds several GB of RAM and VRAM. `train.ps1` warns
  if it is still up on :8000, and if less than 10 GB RAM is free.
- **`cache_latents_to_disk = true`**: the VAE encodes each image once, to `.npz` files next
  to it, and the VAE leaves memory. Later runs reuse them.
- **`max_data_loader_n_workers = 0`**: on Windows each loader worker is a separate process
  with its own copy of torch (1–2 GB each). With cached latents there is nothing for them
  to do anyway.
- **`-LowRam`** adds `--lowram`: loads the model straight to the GPU rather than staging
  it in RAM. Use it on 16 GB if the run dies while loading.
- **`-LowVram`** adds `--fp8_base`: the frozen base weights in fp8, about 3 GB less VRAM.
  For 12 GB cards; slight quality cost, fine for a LoRA.
- **`-NoSamples`** skips the in-training sample renders.
- Windows page file: let it grow to at least 32 GB (System → Advanced → Performance →
  Virtual memory). Otherwise a load-time spike is a crash, not a slowdown.

Expected on 12 GB with defaults: ~10–11 GB VRAM, roughly 1.5–2.5 s/step, so 2,160 steps is
about 1–1.5 h plus samples.
