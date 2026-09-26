"""Curate Aster's LoRA v2 dataset: contact sheet -> selection.json -> bucketed images.

PC-side, stdlib only; uses Pillow when it is installed (much faster, and reads JPEG/WebP).

    # 1. Scan candidates, dedupe, write a contact sheet to score in a browser
    python curate.py sheet --src "C:\\...\\ComfyUI\\output::ASTER_*" --src C:\\Users\\GH-DA\\Aster\\sprites --work C:\\Users\\GH-DA\\lora-v2\\work

    # 2. Open work\\contact_sheet.html, score every image, press "Download selection.json",
    #    save it into the work folder.

    # 3. Resize/pad the kept images into the training folder (and report the mix)
    python curate.py build --selection work\\selection.json --dataset C:\\Users\\GH-DA\\lora-v2\\dataset

The browser can only *download* selection.json; the Python side re-checks every rule, so
a hand-edited selection cannot sneak a two-tailed image into the dataset.
"""

import argparse
import html
import json
import math
import re
import struct
import sys
import zlib
from pathlib import Path

try:  # optional
    from PIL import Image
    HAVE_PIL = True
except ImportError:  # pragma: no cover - depends on the machine
    Image = None
    HAVE_PIL = False

HERE = Path(__file__).resolve().parent
CANON = HERE / "canon_tags.json"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
# SDXL's standard training buckets (~1 megapixel, sides multiple of 64). kohya re-buckets
# anyway; pre-sizing to exactly these means it never has to crop, so a tail near the edge
# of the frame is never cut off.
SDXL_BUCKETS = [(1024, 1024), (1152, 896), (896, 1152), (1216, 832), (832, 1216),
                (1344, 768), (768, 1344), (1536, 640), (640, 1536)]
DUP_THRESHOLD = 6          # dHash bits (of 64) at or below which two images are duplicates
FLATTEN_BG = (255, 255, 255)  # transparent chibi cutouts are laid on white
# Shots that show the tail: here the tail checks must be an explicit pass, never "n/a".
TAIL_SHOTS = {"full_front", "back_view", "side_view", "tail_closeup"}


def load_canon(path=CANON):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- stdlib raster

class Raster:
    """8-bit pixels, row-major, `ch` channels (3 = RGB, 4 = RGBA)."""

    def __init__(self, w, h, ch, data):
        self.w, self.h, self.ch, self.data = w, h, ch, bytearray(data)
        if len(self.data) != w * h * ch:
            raise ValueError("raster size mismatch")


class Unsupported(Exception):
    pass


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def png_read(path):
    """Decode a non-interlaced 8/16-bit PNG to an RGBA Raster. Stdlib only."""
    raw = Path(path).read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise Unsupported(f"not a PNG: {path}")
    pos, idat, palette, trns = 8, [], None, None
    w = h = depth = ctype = None
    while pos < len(raw):
        (n,) = struct.unpack(">I", raw[pos:pos + 4])
        kind, body = raw[pos + 4:pos + 8], raw[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if interlace:
                raise Unsupported(f"interlaced PNG needs Pillow: {path}")
        elif kind == b"PLTE":
            palette = body
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if chans is None or depth not in (8, 16) or (ctype == 3 and depth != 8):
        raise Unsupported(f"PNG colour type {ctype} / depth {depth} needs Pillow: {path}")
    sample = depth // 8
    bpp = chans * sample
    stride = w * bpp
    data = zlib.decompress(b"".join(idat))
    prev = bytearray(stride)
    rows = bytearray()
    i = 0
    for _ in range(h):
        f = data[i]
        cur = bytearray(data[i + 1:i + 1 + stride])
        i += 1 + stride
        if f == 1:
            for x in range(bpp, stride):
                cur[x] = (cur[x] + cur[x - bpp]) & 255
        elif f == 2:
            for x in range(stride):
                cur[x] = (cur[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                left = cur[x - bpp] if x >= bpp else 0
                cur[x] = (cur[x] + ((left + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                left = cur[x - bpp] if x >= bpp else 0
                up_left = prev[x - bpp] if x >= bpp else 0
                cur[x] = (cur[x] + _paeth(left, prev[x], up_left)) & 255
        rows += cur
        prev = cur
    if sample == 2:  # keep the high byte of each 16-bit sample
        rows = rows[0::2]
    out = bytearray(w * h * 4)
    n = w * h
    if ctype == 6:
        out[:] = rows
    elif ctype == 2:
        out[0::4], out[1::4], out[2::4] = rows[0::3], rows[1::3], rows[2::3]
        out[3::4] = b"\xff" * n
    elif ctype == 0:
        out[0::4] = out[1::4] = out[2::4] = rows
        out[3::4] = b"\xff" * n
    elif ctype == 4:
        out[0::4] = out[1::4] = out[2::4] = rows[0::2]
        out[3::4] = rows[1::2]
    else:  # palette
        alpha = trns or b""
        for k, idx in enumerate(rows):
            out[k * 4:k * 4 + 3] = palette[idx * 3:idx * 3 + 3]
            out[k * 4 + 3] = alpha[idx] if idx < len(alpha) else 255
    return Raster(w, h, 4, out)


def png_write(path, r):
    """Write an RGB or RGBA Raster as PNG (filter 0). Stdlib only."""
    ctype = {3: 2, 4: 6}[r.ch]
    stride = r.w * r.ch
    body = bytearray()
    for y in range(r.h):
        body.append(0)
        body += r.data[y * stride:(y + 1) * stride]

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    Path(path).write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", r.w, r.h, 8, ctype, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(body), 6))
        + chunk(b"IEND", b""))


def _weights(src_len, dst_len):
    """Triangle-filter taps per output index; antialiased when shrinking."""
    scale = src_len / dst_len
    support = max(1.0, scale)
    taps = []
    for i in range(dst_len):
        centre = (i + 0.5) * scale
        lo = max(0, int(math.floor(centre - support)))
        hi = min(src_len, int(math.ceil(centre + support)))
        ws = [(j, max(0.0, 1.0 - abs((j + 0.5 - centre) / support))) for j in range(lo, hi)]
        ws = [(j, wt) for j, wt in ws if wt > 0] or [(min(src_len - 1, int(centre)), 1.0)]
        total = sum(wt for _, wt in ws)
        taps.append([(j, wt / total) for j, wt in ws])
    return taps


def resize(r, w, h):
    """Separable triangle resample. Slow in pure Python; Pillow is used when present."""
    ch = r.ch
    tx = _weights(r.w, w)
    mid = bytearray(w * r.h * ch)
    for y in range(r.h):
        row = r.data[y * r.w * ch:(y + 1) * r.w * ch]
        base = y * w * ch
        for x, taps in enumerate(tx):
            for c in range(ch):
                v = 0.0
                for j, wt in taps:
                    v += row[j * ch + c] * wt
                mid[base + x * ch + c] = min(255, max(0, int(v + 0.5)))
    ty = _weights(r.h, h)
    out = bytearray(w * h * ch)
    rs = w * ch
    for y, taps in enumerate(ty):
        base = y * rs
        for k in range(rs):
            v = 0.0
            for j, wt in taps:
                v += mid[j * rs + k] * wt
            out[base + k] = min(255, max(0, int(v + 0.5)))
    return Raster(w, h, ch, out)


def flatten(r, bg=FLATTEN_BG):
    """RGBA -> RGB over a flat colour. Returns (raster, had_transparency)."""
    if r.ch == 3:
        return r, False
    out = bytearray(r.w * r.h * 3)
    had = False
    d = r.data
    for k in range(r.w * r.h):
        a = d[k * 4 + 3]
        if a == 255:
            out[k * 3:k * 3 + 3] = d[k * 4:k * 4 + 3]
        else:
            had = True
            for c in range(3):
                out[k * 3 + c] = (d[k * 4 + c] * a + bg[c] * (255 - a) + 127) // 255
    return Raster(r.w, r.h, 3, out), had


def border_mean(r):
    """Mean RGB of the outermost pixel ring: the pad colour that blends with the image."""
    pts = [(x, 0) for x in range(r.w)] + [(x, r.h - 1) for x in range(r.w)]
    pts += [(0, y) for y in range(r.h)] + [(r.w - 1, y) for y in range(r.h)]
    acc = [0, 0, 0]
    for x, y in pts:
        o = (y * r.w + x) * r.ch
        for c in range(3):
            acc[c] += r.data[o + c]
    return tuple(round(a / len(pts)) for a in acc)


def image_size(path):
    with Image.open(path) as im:
        return im.size


def load_raster(path, max_side=None):
    """-> RGBA Raster. Pillow if available (any format), else stdlib PNG."""
    if HAVE_PIL:
        with Image.open(path) as im:
            im = im.convert("RGBA")
            if max_side and max(im.size) > max_side:
                im.thumbnail((max_side, max_side), Image.BOX)
            return Raster(im.width, im.height, 4, im.tobytes())
    if Path(path).suffix.lower() != ".png":
        raise Unsupported(f"{Path(path).name}: only PNG without Pillow (pip install pillow)")
    return png_read(path)


# ---------------------------------------------------------------- dedupe

def dhash(r):
    """64-bit difference hash: 9x8 greyscale grid, one bit per horizontal step."""
    gw, gh = 9, 8
    rgb, _ = flatten(r) if r.ch == 4 else (r, False)
    step = max(1, min(rgb.w, rgb.h) // 64)  # sample sparsely: speed, not accuracy, matters
    grid = []
    for gy in range(gh):
        y0, y1 = gy * rgb.h // gh, max(gy * rgb.h // gh + 1, (gy + 1) * rgb.h // gh)
        for gx in range(gw):
            x0, x1 = gx * rgb.w // gw, max(gx * rgb.w // gw + 1, (gx + 1) * rgb.w // gw)
            tot = cnt = 0
            for y in range(y0, y1, step):
                o = y * rgb.w * 3
                for x in range(x0, x1, step):
                    p = o + x * 3
                    tot += 299 * rgb.data[p] + 587 * rgb.data[p + 1] + 114 * rgb.data[p + 2]
                    cnt += 1
            grid.append(tot / max(cnt, 1))
    bits = 0
    for gy in range(gh):
        for gx in range(gw - 1):
            bits = (bits << 1) | (1 if grid[gy * gw + gx] < grid[gy * gw + gx + 1] else 0)
    return bits


def hamming(a, b):
    return bin(a ^ b).count("1")


def group_duplicates(hashes, threshold=DUP_THRESHOLD):
    """hashes: list of int|None -> list of group ids (union-find; None never groups)."""
    parent = list(range(len(hashes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, hi in enumerate(hashes):
        if hi is None:
            continue
        for j in range(i):
            if hashes[j] is not None and hamming(hi, hashes[j]) <= threshold:
                parent[find(i)] = find(j)
    roots, out = {}, []
    for i in range(len(hashes)):
        out.append(roots.setdefault(find(i), len(roots)))
    return out


# ---------------------------------------------------------------- buckets

def pick_bucket(w, h, buckets=None):
    """The bucket whose aspect ratio is closest (in log space) to the image's."""
    buckets = buckets or SDXL_BUCKETS
    ar = math.log(w / h)
    return min(buckets, key=lambda b: abs(math.log(b[0] / b[1]) - ar))


def fit_pad(r, bucket, pad):
    """Scale to fit inside the bucket (never crop), centre, pad the rest. RGB in, RGB out."""
    bw, bh = bucket
    s = min(bw / r.w, bh / r.h)
    nw, nh = max(1, min(bw, round(r.w * s))), max(1, min(bh, round(r.h * s)))
    if HAVE_PIL:
        im = Image.frombytes("RGB", (r.w, r.h), bytes(r.data)).resize((nw, nh), Image.LANCZOS)
        canvas = Image.new("RGB", (bw, bh), tuple(pad))
        canvas.paste(im, ((bw - nw) // 2, (bh - nh) // 2))
        return Raster(bw, bh, 3, canvas.tobytes())
    small = resize(r, nw, nh) if (nw, nh) != (r.w, r.h) else r
    out = bytearray(bytes(pad) * (bw * bh))
    ox, oy = (bw - nw) // 2, (bh - nh) // 2
    for y in range(nh):
        dst = ((oy + y) * bw + ox) * 3
        out[dst:dst + nw * 3] = small.data[y * nw * 3:(y + 1) * nw * 3]
    return Raster(bw, bh, 3, out)


def save_png(path, r):
    if HAVE_PIL:
        Image.frombytes("RGB" if r.ch == 3 else "RGBA", (r.w, r.h), bytes(r.data)).save(path)
    else:
        png_write(path, r)


# ---------------------------------------------------------------- scan / sheet

def parse_src(spec):
    """'DIR' or 'DIR::GLOB' (or a single file) -> list of image paths, sorted."""
    folder, _, pattern = spec.partition("::")
    p = Path(folder)
    if p.is_file():
        return [p]
    if not p.is_dir():
        raise SystemExit(f"source not found: {folder}")
    return sorted(q for q in p.glob(pattern or "*")
                  if q.is_file() and q.suffix.lower() in IMAGE_EXTS)


def guess_form(name):
    n = name.lower()
    return "chibi" if ("_cut" in n or "chibi" in n) else "full"


def guess_shot(name):
    n = name.lower()
    for key, shot in (("back", "back_view"), ("behind", "back_view"), ("side", "side_view"),
                      ("tail_close", "tail_closeup"), ("paws", "paws_closeup"),
                      ("face", "upper_body"), ("portrait", "upper_body"),
                      ("sleepy", "upper_body")):
        if key in n and "_cut" not in n:
            return shot
    return "full_front"


def scan(specs, work, threshold=DUP_THRESHOLD, log=print):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    paths, seen = [], set()
    for spec in specs:
        for p in parse_src(spec):
            if p.resolve() not in seen:
                seen.add(p.resolve())
                paths.append(p)
    if not paths:
        raise SystemExit("no candidate images found")
    thumbs = work / "thumbs"
    if HAVE_PIL:
        thumbs.mkdir(exist_ok=True)
    hashes, cands = [], []
    for n, p in enumerate(paths, 1):
        cid = f"c{n:03d}"
        try:
            r = load_raster(p, max_side=512)
            hashes.append(dhash(r))
            size = list(image_size(p)) if HAVE_PIL else [r.w, r.h]  # r may be a thumbnail
        except (Unsupported, OSError, zlib.error, ValueError) as e:
            log(f"  can't read {p.name} ({e}); listed without dedupe")
            hashes.append(None)
            size = None
        thumb = p.resolve().as_uri()
        if HAVE_PIL:
            try:
                with Image.open(p) as im:
                    im = im.convert("RGBA")
                    im.thumbnail((360, 360))
                    bg = Image.new("RGBA", im.size, FLATTEN_BG + (255,))
                    bg.alpha_composite(im)
                    bg.convert("RGB").save(thumbs / f"{cid}.jpg", quality=85)
                    thumb = f"thumbs/{cid}.jpg"
            except OSError:
                pass
        cands.append({"id": cid, "path": str(p.resolve()), "name": p.name, "thumb": thumb,
                      "uri": p.resolve().as_uri(), "size": size,
                      "form": guess_form(p.stem), "shot": guess_shot(p.stem)})
        if n % 25 == 0:
            log(f"  hashed {n}/{len(paths)}")
    groups = group_duplicates(hashes, threshold)
    first = {}
    for c, g in zip(cands, groups):
        c["dup_group"] = g
        c["dup_of"] = first.get(g)  # None for the first of each group
        first.setdefault(g, c["id"])
    return cands


def write_sheet(cands, work, canon):
    work = Path(work)
    (work / "candidates.json").write_text(json.dumps(cands, indent=1), encoding="utf-8")
    data = json.dumps({"candidates": cands, "checklist": canon["checklist"],
                       "exclude": canon["exclude"], "shots": canon["shots"],
                       "mix": canon["mix"], "sheet": str(work.resolve())})
    page = SHEET_HTML.replace("__DATA__", data.replace("</", "<\\/"))
    out = work / "contact_sheet.html"
    out.write_text(page, encoding="utf-8")
    return out


# ---------------------------------------------------------------- selection rules

def entry_problems(e, canon):
    """Why this selection entry may not go into the dataset. Empty list = it may."""
    probs = []
    if not e.get("keep"):
        return ["not kept"]
    if e.get("form") not in canon["forms"]:
        probs.append(f"form must be one of {sorted(canon['forms'])}")
    if e.get("shot") not in canon["shots"]:
        probs.append(f"shot must be one of {sorted(canon['shots'])}")
    known_ex = {x["id"] for x in canon["exclude"]}
    for x in e.get("exclude") or []:
        probs.append(f"excluded: {x}" if x in known_ex else f"unknown exclusion: {x}")
    checks = e.get("checks") or {}
    for item in canon["checklist"]:
        v = checks.get(item["id"], "")
        if v == "fail":
            probs.append(f"fails: {item['id']}")
        elif v not in ("pass", "na"):
            probs.append(f"not scored: {item['id']}")
    if e.get("shot") in TAIL_SHOTS:
        for t in ("one_tail", "marigold_band"):
            if checks.get(t) == "na":
                probs.append(f"{t} must be a pass in a {e['shot']} shot (the tail is in frame)")
    return probs


def mix_report(kept, canon):
    """Warnings about the kept set against canon_tags.json -> mix. Advisory only."""
    mix, warn = canon["mix"], []

    def rng(label, n, lo_hi):
        lo, hi = lo_hi
        if not lo <= n <= hi:
            warn.append(f"{label}: {n} (target {lo}-{hi})")

    rng("total", len(kept), mix["total"])
    for form, lim in mix["form"].items():
        rng(f"form {form}", sum(1 for e in kept if e["form"] == form), lim)
    for shot, lim in mix["shot"].items():
        rng(f"shot {shot}", sum(1 for e in kept if e["shot"] == shot), lim)
    if kept:
        outfits = {}
        for e in kept:
            o = (e.get("outfit") or "").strip().lower()
            if o:
                outfits[o] = outfits.get(o, 0) + 1
        for o, n in outfits.items():
            if n / len(kept) > mix["max_share_one_outfit"]:
                warn.append(f"outfit '{o}' is {n}/{len(kept)} of the set "
                            f"(max {mix['max_share_one_outfit']:.0%}); it will bake into her identity")
    return warn


def build(selection, dataset, canon, allow_dups=False, dry_run=False, log=print):
    sel = json.loads(Path(selection).read_text(encoding="utf-8"))
    entries = sel["images"] if isinstance(sel, dict) else sel
    kept, used_groups, names = [], {}, set()
    for e in entries:
        probs = entry_problems(e, canon)
        if probs == ["not kept"]:
            continue
        if probs:
            log(f"  refuse {Path(e['path']).name}: " + "; ".join(probs))
            continue
        g = e.get("dup_group")
        if g is not None and g in used_groups and not allow_dups:
            log(f"  refuse {Path(e['path']).name}: near-duplicate of {used_groups[g]}")
            continue
        used_groups.setdefault(g, Path(e["path"]).name)
        kept.append(e)
    for w in mix_report(kept, canon):
        log(f"  mix: {w}")
    if dry_run:
        log(f"{len(kept)} images would be written")
        return kept
    dataset = Path(dataset)
    dataset.mkdir(parents=True, exist_ok=True)
    meta = {}
    for e in kept:
        src = Path(e["path"])
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", src.stem)
        name, k = f"{stem}.png", 2
        while name in names:
            name, k = f"{stem}-{k}.png", k + 1
        names.add(name)
        rgb, had_alpha = flatten(load_raster(src))
        pad = FLATTEN_BG if had_alpha else border_mean(rgb)
        bucket = pick_bucket(rgb.w, rgb.h)
        save_png(dataset / name, fit_pad(rgb, bucket, pad))
        meta[name] = {"source": str(src), "source_stem": src.stem, "form": e["form"],
                      "shot": e["shot"], "outfit": e.get("outfit", ""),
                      "tags": e.get("tags", ""), "checks": e.get("checks", {}),
                      "flattened": had_alpha, "bucket": list(bucket)}
        log(f"  {name}  {rgb.w}x{rgb.h} -> {bucket[0]}x{bucket[1]}")
    (dataset / "_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    log(f"{len(kept)} images in {dataset}; next: python caption.py --dataset {dataset}")
    return kept


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sheet", help="scan + dedupe candidates, write contact_sheet.html")
    s.add_argument("--src", action="append", required=True, metavar="DIR[::GLOB]",
                   help="folder (optionally ::glob, e.g. output::ASTER_*) or file; repeatable")
    s.add_argument("--work", required=True, help="folder for the sheet, thumbs, selection.json")
    s.add_argument("--threshold", type=int, default=DUP_THRESHOLD,
                   help=f"dHash bits for 'duplicate' (default {DUP_THRESHOLD}; 0 = identical only)")
    b = sub.add_parser("build", help="resize/pad the kept images into the dataset folder")
    b.add_argument("--selection", required=True)
    b.add_argument("--dataset", required=True)
    b.add_argument("--allow-dups", action="store_true", help="keep several of one near-duplicate group")
    b.add_argument("--dry-run", action="store_true", help="validate and report the mix; write nothing")
    args = ap.parse_args(argv)
    canon = load_canon()
    if not HAVE_PIL:
        print("(Pillow not found: using the stdlib PNG path — correct but slow. pip install pillow)")
    if args.cmd == "sheet":
        cands = scan(args.src, args.work, args.threshold)
        out = write_sheet(cands, args.work, canon)
        dups = sum(1 for c in cands if c["dup_of"])
        print(f"{len(cands)} candidates, {dups} near-duplicates flagged -> {out}")
        return 0
    build(args.selection, args.dataset, canon, args.allow_dups, args.dry_run)
    return 0


SHEET_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aster LoRA v2 curation</title>
<style>
:root{--bg:#faf7f2;--fg:#2b2233;--card:#fff;--line:#ddd3e6;--ok:#2e7d4f;--bad:#b3261e;--mute:#7a6f85;--acc:#6b4fa0}
@media (prefers-color-scheme:dark){:root{--bg:#17131c;--fg:#ece6f2;--card:#221c29;--line:#3a3145;--ok:#7fd49c;--bad:#ff8a80;--mute:#a497b3;--acc:#c3a6ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif}
header{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px}
h1{font-size:16px;margin:0 0 6px}button,select,input{font:inherit;color:inherit}
button{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 10px;cursor:pointer}
#summary{font-size:12px;color:var(--mute);margin-top:6px}#summary b.bad{color:var(--bad)}#summary b.ok{color:var(--ok)}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;padding:12px 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}
.card.keep{outline:2px solid var(--ok)}.card.dup{opacity:.75}
.card img{width:100%;height:300px;object-fit:contain;background:#0001;border-radius:6px}
.name{font-size:12px;word-break:break-all;color:var(--mute)}.row{display:flex;gap:6px;align-items:center;margin:4px 0;flex-wrap:wrap}
.chk{display:grid;grid-template-columns:1fr auto;gap:2px 6px;font-size:12px;margin:6px 0}
.chk select{font-size:12px}.pass{color:var(--ok)}.fail{color:var(--bad)}
.ex label{font-size:12px;display:block}.probs{color:var(--bad);font-size:12px}.okmsg{color:var(--ok);font-size:12px}
.badge{font-size:11px;border:1px solid var(--line);border-radius:4px;padding:0 4px}
input[type=text]{width:100%;background:transparent;border:1px solid var(--line);border-radius:4px;padding:2px 4px}
</style></head><body>
<header><h1>Aster LoRA v2 &mdash; curation</h1>
<div class="row">
<button id="dl">Download selection.json</button>
<label><button id="ldb" type="button">Load selection.json</button><input id="ld" type="file" accept=".json" hidden></label>
<select id="filter"><option value="all">show all</option><option value="keep">kept</option><option value="open">undecided</option><option value="nodup">hide duplicates</option></select>
<button id="reset">Reset</button></div>
<div id="summary"></div></header>
<main id="grid"></main>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const KEY = 'aster-curate:' + D.sheet;
const TAIL_SHOTS = new Set(['full_front','back_view','side_view','tail_closeup']);
function fresh(){ return D.candidates.map(c => ({id:c.id, path:c.path, form:c.form, shot:c.shot,
  outfit:'', tags:'', keep:false, checks:{}, exclude:[], dup_group:c.dup_group})); }
let S; try { S = JSON.parse(localStorage.getItem(KEY)) } catch(e) {}
if (!Array.isArray(S) || S.length !== D.candidates.length) S = fresh();
function save(){ try { localStorage.setItem(KEY, JSON.stringify(S)) } catch(e) {} }
function problems(e){
  const p = [];
  (e.exclude||[]).forEach(x => p.push('excluded: ' + x));
  D.checklist.forEach(i => { const v = e.checks[i.id] || '';
    if (v === 'fail') p.push('fails: ' + i.id); else if (!v) p.push('not scored: ' + i.id); });
  if (TAIL_SHOTS.has(e.shot)) ['one_tail','marigold_band'].forEach(t => {
    if (e.checks[t] === 'na') p.push(t + ' must pass in this shot'); });
  return p;
}
function opt(v, label, cur){ return `<option value="${v}"${v===cur?' selected':''}>${label}</option>`; }
function esc(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function card(c, e){
  const p = problems(e);
  const checks = D.checklist.map(i => { const v = e.checks[i.id] || '';
    return `<span title="${esc(i.label)}" class="${v}">${esc(i.label.split(':')[0])}</span>
      <select data-k="check" data-c="${i.id}">${opt('','?',v)}${opt('pass','pass',v)}${opt('fail','fail',v)}${opt('na','n/a',v)}</select>`; }).join('');
  const ex = D.exclude.map(x => `<label><input type="checkbox" data-k="ex" data-c="${x.id}"${e.exclude.includes(x.id)?' checked':''}> ${esc(x.label)}</label>`).join('');
  const shots = Object.entries(D.shots).map(([k,v]) => opt(k, v.label, e.shot)).join('');
  return `<div class="card${e.keep?' keep':''}${c.dup_of?' dup':''}" data-i="${c.id}">
    <a href="${esc(c.uri)}" target="_blank"><img loading="lazy" src="${esc(c.thumb)}" alt=""></a>
    <div class="name">${esc(c.id)} &middot; ${esc(c.name)} ${c.size?'&middot; '+c.size.join('x'):''}
      ${c.dup_of?`<span class="badge">near-duplicate of ${esc(c.dup_of)}</span>`:''}</div>
    <div class="row"><select data-k="form">${opt('full','full',e.form)}${opt('chibi','chibi',e.form)}</select>
      <select data-k="shot">${shots}</select></div>
    <div class="row"><input type="text" data-k="outfit" placeholder="outfit (e.g. lavender cable-knit sweater)" value="${esc(e.outfit)}"></div>
    <div class="chk">${checks}</div>
    <div class="ex">${ex}</div>
    <div class="row"><input type="text" data-k="tags" placeholder="extra caption tags (optional)" value="${esc(e.tags)}"></div>
    <div class="row"><label><input type="checkbox" data-k="keep"${e.keep?' checked':''}> <b>keep</b></label></div>
    ${e.keep ? (p.length ? `<div class="probs">${p.map(esc).join('<br>')}</div>` : '<div class="okmsg">ok to train</div>') : ''}
  </div>`;
}
function summary(){
  const kept = S.filter(e => e.keep && !problems(e).length);
  const n = (f) => kept.filter(f).length;
  const rng = (label, v, lh) => `${label} <b class="${v>=lh[0]&&v<=lh[1]?'ok':'bad'}">${v}</b>/${lh[0]}-${lh[1]}`;
  const parts = [rng('total', kept.length, D.mix.total)];
  Object.entries(D.mix.form).forEach(([k,lh]) => parts.push(rng(k, n(e => e.form===k), lh)));
  Object.entries(D.mix.shot).forEach(([k,lh]) => parts.push(rng(k, n(e => e.shot===k), lh)));
  const bad = S.filter(e => e.keep && problems(e).length).length;
  document.getElementById('summary').innerHTML = parts.join(' &middot; ') + (bad ? ` &middot; <b class="bad">${bad} kept but failing</b>` : '');
}
function render(){
  const f = document.getElementById('filter').value;
  const byId = Object.fromEntries(S.map(e => [e.id, e]));
  document.getElementById('grid').innerHTML = D.candidates.filter(c => {
    const e = byId[c.id];
    return f === 'all' || (f === 'keep' && e.keep) || (f === 'open' && !e.keep) || (f === 'nodup' && !c.dup_of);
  }).map(c => card(c, byId[c.id])).join('');
  summary();
}
document.getElementById('grid').addEventListener('change', ev => {
  const t = ev.target, cardEl = t.closest('.card'); if (!cardEl) return;
  const e = S.find(x => x.id === cardEl.dataset.i), k = t.dataset.k;
  if (k === 'check') e.checks[t.dataset.c] = t.value;
  else if (k === 'ex') e.exclude = t.checked ? [...new Set([...e.exclude, t.dataset.c])] : e.exclude.filter(x => x !== t.dataset.c);
  else if (k === 'keep') e.keep = t.checked;
  else e[k] = t.value;
  save(); render();
});
document.getElementById('filter').onchange = render;
document.getElementById('reset').onclick = () => { if (confirm('Clear every score?')) { S = fresh(); save(); render(); } };
document.getElementById('dl').onclick = () => {
  const blob = new Blob([JSON.stringify({version:1, sheet:D.sheet, images:S}, null, 1)], {type:'application/json'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'selection.json'; a.click();
};
document.getElementById('ldb').onclick = () => document.getElementById('ld').click();
document.getElementById('ld').onchange = ev => { const f = ev.target.files[0]; if (!f) return;
  f.text().then(t => { const j = JSON.parse(t), got = Object.fromEntries((j.images||j).map(e => [e.id, e]));
    S = fresh().map(e => Object.assign(e, got[e.id] || {})); save(); render(); }); };
render();
</script></body></html>
"""


if __name__ == "__main__":
    sys.exit(main())
