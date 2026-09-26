"""Write kohya-style .txt captions for Aster's LoRA v2 dataset. Stdlib only.

    python caption.py --dataset C:\\Users\\GH-DA\\lora-v2\\dataset
    python caption.py --dataset ... --dry-run                   # print, write nothing
    python caption.py --dataset ... --config train_config\\dataset.toml   # cross-check keep_tokens

Every caption is assembled in one fixed order:

    asterfen, [form tags], [locked canon tags], [per-image variable tags]

* trigger    -- canon_tags.json "trigger". Always first.
* form       -- "chibi, super deformed" for the chibi form; nothing for the full form.
* locked     -- every tag in canon_tags.json "locked", in file order. The sweater entry is
                conditional: "lavender sweater" is added only when the image's own tags
                mention a sweater. With --drop-hidden, a trait the curator scored "n/a"
                (not in frame) is left out, e.g. no tail tags on a face close-up.
* variable   -- outfit, pose, setting, shot. Taken from, in priority order:
                overrides.json (per image) > curate.py's selection (shot, outfit, extra
                tags) > the scene text in sprite-regen/sprites.json or eval_prompts.txt
                matched from the filename.

--shuffle-keep N (default 1) must equal `keep_tokens` in the kohya dataset config. kohya
shuffles the comma-separated tags of every caption each step (shuffle_caption = true) but
never moves the first N. With N = 1 only `asterfen` is pinned, so the trigger always leads
while the canon and variable tags are shuffled and none of them becomes positional. N = 2
would also pin the next tag -- "chibi" on chibi images, but "anthro" on full ones, since
the full form has no form tag -- which is why 1 is the recommended value.

Banned phrases (canon_tags.json "banned_substrings"/"banned_tags" -- persona metaphors like
"many arms for parallel work", two tails, brown eyes, coral) are stripped from variable tags
with a warning, and a finished caption that still contains one is an error.
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANON = HERE / "canon_tags.json"
SPRITES = HERE.parent / "sprite-regen" / "sprites.json"
EVAL_PROMPTS = HERE / "eval_prompts.txt"
OVERRIDES = HERE / "overrides.json"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

REGEN_RE = re.compile(r"^ASTER_regen-\d{8}-\d{4}_(?P<name>.+?)_d\d+_s\d+(?:_\d+_?)?$")
COMPARE_RE = re.compile(r"^ASTER_compare-\d{8}-\d{4}_(?P<lora>[^_]+)_(?P<pid>.+?)_s\d+(?:_\d+_?)?$")
FRAME_RE = re.compile(r"^(?P<clip>[a-z]+)_(?P<n>\d{2})_cut$")
COUNTER_RE = re.compile(r"_\d{5}_?$")  # ComfyUI's SaveImage counter
WEIGHT_RE = re.compile(r"\(([^():]+?)(?::[\d.]+)?\)")
# Scene phrases that are render instructions, not descriptions of the picture.
NOT_CAPTIONS = {"no scenery", "same scale and baseline as idle"}


class CaptionError(Exception):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def split_tags(text):
    """'a, (b:1.2), c' -> ['a', 'b', 'c'], lower-cased, weights and brackets stripped."""
    if not text:
        return []
    if isinstance(text, (list, tuple)):
        text = ", ".join(text)
    text = WEIGHT_RE.sub(r"\1", text)
    out = []
    for t in text.split(","):
        t = re.sub(r"\s+", " ", t.strip().strip("()").strip()).lower()
        if t and t not in NOT_CAPTIONS:
            out.append(t)
    return out


def dedupe(tags):
    seen, out = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def banned_hits(tags, canon):
    """-> list of (tag, reason) for every banned phrase or banned exact tag."""
    hits = []
    subs = [s.lower() for s in canon["banned_substrings"]]
    exact = {t.lower() for t in canon["banned_tags"]}
    for t in tags:
        if t in exact:
            hits.append((t, "banned tag"))
            continue
        for s in subs:
            if s in t:
                hits.append((t, f"contains '{s}'"))
                break
    return hits


def load_eval_prompts(path=EVAL_PROMPTS):
    """eval_prompts.txt -> list of {id, mode, text}. Lines: `id | mode | text`, # comments."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|", 2)]
        if len(parts) != 3 or parts[1] not in ("bare", "canon"):
            raise ValueError(f"bad eval prompt line: {line!r}")
        out.append({"id": parts[0], "mode": parts[1], "text": parts[2]})
    return out


def scene_from_name(stem, sprites, evals):
    """Filename stem -> (form or None, [variable tags]) from sprites.json / eval prompts."""
    stem = COUNTER_RE.sub("", stem)
    regen = False
    m = COMPARE_RE.match(stem)
    if m:
        for p in evals:
            if p["id"] == m.group("pid"):
                form = "chibi" if "chibi" in p["text"] else None
                return form, split_tags(p["text"])
        return None, []
    m = REGEN_RE.match(stem)
    if m:
        stem, regen = m.group("name"), True
    chibi = sprites["chibi"]
    for e in sprites["full"]:
        if e["name"] == stem:
            return "full", split_tags(e["scene"])
    bg = ["simple background", "green background"] if regen else []
    for e in chibi["frames"]:
        if e["name"] == stem:
            return "chibi", split_tags(chibi["prefix"]) + split_tags(e["scene"]) + bg
    m = FRAME_RE.match(stem)
    if m:
        for c in sprites["frames"]["clips"]:
            n = int(m.group("n"))
            if c["clip"] == m.group("clip") and 1 <= n <= len(c["poses"]):
                return "chibi", split_tags(chibi["prefix"]) + split_tags(c["poses"][n - 1]) + bg
    return None, []


def locked_tags(canon, variable, checks=None, drop_hidden=False):
    out = []
    joined = " ".join(variable)
    for group in canon["locked"]:
        when = group.get("when")
        if when and when not in joined:
            continue
        if drop_hidden and checks and group.get("check") and checks.get(group["check"]) == "na":
            continue
        out.extend(t.lower() for t in group["tags"])
    return out


def assemble(canon, form, variable, checks=None, drop_hidden=False, log=None):
    """The caption for one image, as a list of tags in final order."""
    if form not in canon["forms"]:
        raise CaptionError(f"unknown form {form!r}")
    clean = []
    for t in dedupe(variable):
        hit = banned_hits([t], canon)
        if hit:
            if log:
                log(f"    dropped '{t}': {hit[0][1]}")
            continue
        clean.append(t)
    head = [canon["trigger"]] + [t.lower() for t in canon["forms"][form]]
    tags = dedupe(head + locked_tags(canon, clean, checks, drop_hidden) + clean)
    if tags[0] != canon["trigger"] or canon["trigger"] in tags[1:]:
        raise CaptionError("trigger must be first and appear once")
    bad = banned_hits(tags, canon)
    if bad:
        raise CaptionError(f"banned in caption: {bad}")
    return tags


def rough_tokens(caption):
    """A cheap over-estimate of CLIP tokens (words + punctuation)."""
    return len(re.findall(r"\w+|[^\w\s]", caption))


def read_keep_tokens(config_path):
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        return None
    with open(config_path, "rb") as f:
        cfg = tomllib.load(f)
    for section in [cfg.get("general", {})] + cfg.get("datasets", []):
        if "keep_tokens" in section:
            return section["keep_tokens"]
    return None


def caption_dataset(dataset, canon, sprites, evals, overrides, shuffle_keep=1,
                    drop_hidden=False, dry_run=False, log=print):
    dataset = Path(dataset)
    meta_path = dataset / "_meta.json"
    meta = load_json(meta_path) if meta_path.is_file() else {}
    images = sorted(p for p in dataset.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not images:
        raise SystemExit(f"no images in {dataset}")
    results = {}
    for img in images:
        m = meta.get(img.name, {})
        stems = [img.stem, m.get("source_stem", "")]
        ov = next((overrides[s] for s in stems if s and s in overrides), {})
        form_guess, derived = scene_from_name(m.get("source_stem") or img.stem, sprites, evals)
        form = ov.get("form") or m.get("form") or form_guess or \
            ("chibi" if "_cut" in img.stem or "chibi" in img.stem.lower() else "full")
        variable = split_tags(ov.get("tags"))
        if not ov.get("replace"):
            shot = ov.get("shot") or m.get("shot")
            if shot in canon["shots"]:
                variable += [t.lower() for t in canon["shots"][shot]["tags"]]
            variable += split_tags(m.get("outfit")) + split_tags(m.get("tags"))
            if m.get("flattened"):
                variable += ["simple background", "white background"]
                derived = [t for t in derived if "background" not in t]
            variable += derived
        log(f"  {img.name}")
        tags = assemble(canon, form, variable, m.get("checks"), drop_hidden, log)
        if len(tags) < max(1, shuffle_keep):
            raise CaptionError(f"{img.name}: caption shorter than --shuffle-keep {shuffle_keep}")
        caption = ", ".join(tags)
        if rough_tokens(caption) > 225:
            log(f"    warning: ~{rough_tokens(caption)} tokens; kohya truncates at max_token_length 225")
        results[img.name] = caption
        if not dry_run:
            img.with_suffix(".txt").write_text(caption + "\n", encoding="utf-8")
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dataset", required=True, help="folder of images (from curate.py build)")
    ap.add_argument("--overrides", help=f"per-image overrides JSON (default: {OVERRIDES.name} "
                                        "here, plus DATASET/overrides.json if present)")
    ap.add_argument("--shuffle-keep", type=int, default=1, metavar="N",
                    help="leading tags kohya must not shuffle; must equal keep_tokens (default 1)")
    ap.add_argument("--config", help="kohya dataset TOML to cross-check keep_tokens against")
    ap.add_argument("--drop-hidden", action="store_true",
                    help="omit locked tags for traits scored n/a (not in frame)")
    ap.add_argument("--dry-run", action="store_true", help="print captions, write nothing")
    args = ap.parse_args(argv)

    if args.shuffle_keep < 1:
        print("warning: --shuffle-keep 0 lets kohya move the trigger away from the front",
              file=sys.stderr)
    if args.config:
        kt = read_keep_tokens(args.config)
        if kt is not None and kt != args.shuffle_keep:
            print(f"keep_tokens = {kt} in {args.config} but --shuffle-keep {args.shuffle_keep}; "
                  "make them match", file=sys.stderr)
            return 2
    canon = load_json(CANON)
    overrides = {}
    for p in [Path(args.overrides) if args.overrides else OVERRIDES,
              Path(args.dataset) / "overrides.json"]:
        if p.is_file():
            overrides.update({k: v for k, v in load_json(p).items() if not k.startswith("_")})
    try:
        res = caption_dataset(args.dataset, canon, load_json(SPRITES), load_eval_prompts(),
                              overrides, args.shuffle_keep, args.drop_hidden, args.dry_run)
    except CaptionError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.dry_run:
        for name, cap in res.items():
            print(f"\n{name}\n  {cap}")
    print(f"\n{len(res)} captions{' (dry run)' if args.dry_run else ' written'}; "
          f"keep_tokens must be {args.shuffle_keep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
