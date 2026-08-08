# Aster had no design record anywhere in git

**From:** Claude · **Date:** 2026-08-08 · **Branch:** claude/accessible-aster-render-5lda2l

## What I was doing

The user asked for a good reference render of Aster and was surprised no session had ever
been able to produce one. It turned out no cloud session *could*: her design existed only
on the PC and in a private repo, and nothing describing her had ever been committed to a
file any session loads at boot. This branch fixes that, and adds the tooling to render her
consistently.

## State

**Committed and real:**

- `characters/aster.md` — design sheet. Locked traits, her **two canonical forms** (full
  illustration + desktop chibi), what is free to vary, the documented drift, and the
  evidence table for why cloud text-to-image fails on her.
- `characters/aster-prompt.txt` / `aster-negative.txt` — render prompts. These are the
  mechanical fix: `find_character_files()` in `tools/aster-app/server.py:170` globs
  `characters/*aster*`, and until now found **nothing**, so `renderPrefix` was `None` and
  *every render she has ever had went out with zero character conditioning*. That is the
  root cause of her drift. Kaarten has these files and renders consistently.
- `characters/aster-workflow.json` — API-format ComfyUI graph with her LoRA wired in, using
  the aster-app's `%positive%`/`%negative%`/`%seed%`/… placeholders.
- `docs/aster-render-on-pc.md` — the render batch to run over SSH.
- `CLAUDE.md` — a section describing who she is, so future sessions boot knowing her. This
  is the actual anti-recurrence fix.

**Not done:**

- **There is no `characters/ref/aster-ref.png`.** No reference image is committed. Three
  Comfy Cloud attempts on `bfl/flux-2-pro` all failed (two tails, two tails, no tail) and
  none were kept. The render still needs to happen on the PC.

**Facts worth not rediscovering:**

- Her repo is **`ghdathegabbalion/Aster`** (private) — persona, twelve sprites, companion app.
- LoRA `aster-illustrious-v1.safetensors`, trigger `asterfen`, base
  `furrytoonmix_xlIllustriousV2.safetensors`, local ComfyUI on `:8000`. **Free.**
- Her persona line *"many arms for parallel work"* is a metaphor about concurrency. Image
  models render it literally. Never put it in a prompt.
- `flux-2-pro` ignores top-level `aspect_ratio`; `width`/`height` inside `params` works.

## Open questions

- **Ink-dipped paws** are in the spec as canon, but appear in only one of four full sprites.
  Locking them in means the existing sprite set is partially non-conforming. Accepted on the
  reasoning that "warm above, deep below" should be a rule rather than a one-off — but it is
  a real decision someone could reverse.
- **The orange proposal** is written into the sheet as explicitly *not canon*. Taking it
  means regenerating the sprite set so her app and her sheet stay in sync.
- **Sweater colour** is lavender in some sprites, white in others. Recorded as free to vary;
  could reasonably be locked instead.

## Next step

**Run `docs/aster-render-on-pc.md` from an SSH session and commit the winner as
`characters/ref/aster-ref.png`.** Everything else is staged and waiting on that one image —
it is the piece that turns a written spec into something future sprites can be generated
*from*, which is how Vesper stays visually consistent (two curated PNGs reused, not
regenerated). Aster's whole drift problem is that she never had that anchor.
