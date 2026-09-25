"""Regenerate Aster's sprite set to current canon — img2img off each existing sprite.

Runs on the PC against the local ComfyUI (port 8000), with her LoRA. Stdlib only.

    python regen.py --sprites C:\\Users\\GH-DA\\Aster\\sprites          # everything
    python regen.py --sprites ... --only happy dance                     # a few
    python regen.py --sprites ... --dry-run                              # print, queue nothing
    python regen.py --sprites ... --frames --priority 1                  # animation frames

Renders land in ComfyUI's own output folder under aster/regen-<stamp>/, which the
aster-app gallery already browses. Nothing is written into this repo, and nothing in
the Aster repo is overwritten — picking winners and copying them over is a human step.
See README.md.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHARACTERS = HERE.parent
MANIFEST = HERE / "sprites.json"

DEFAULT_COMFY = "http://127.0.0.1:8000"
DEFAULT_MODEL = "furrytoonmix_xlIllustriousV2.safetensors"
DEFAULT_LORA = "aster-illustrious-v1.safetensors"
LORA_STRENGTH = 0.8
SEED_BASE = 20260925

# Where her repo usually sits on the PC, tried in order when --sprites is not given.
SPRITE_DIRS = [
    r"C:\Users\GH-DA\Aster\sprites",
    r"C:\Users\GH-DA\aster\sprites",
    str(CHARACTERS.parent.parent / "Aster" / "sprites"),
    str(CHARACTERS.parent.parent / "aster" / "sprites"),
]


def read_prompt(path):
    """A prompt file minus its '#' comment lines, flattened to one line.

    The comments in aster-prompt.txt name the exact phrases that break her renders
    ("many arms for parallel work"), so they must never reach the text encoder.
    """
    lines = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("#"):
            continue
        if line.strip():
            lines.append(line.strip())
    return " ".join(lines)


def load_manifest(path=MANIFEST):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def plan_jobs(manifest, only=None, seeds=None, denoise=None, seed_base=SEED_BASE):
    """Expand the manifest into one job per (sprite, denoise, seed).

    Seeds are the same list for every sprite, so the two wave frames — which the pet
    animates between — get matching seeds and can be picked as a pair.
    """
    d = manifest["defaults"]
    n_seeds = seeds or d["seeds"]
    chibi = manifest["chibi"]
    entries = [dict(e, form="full") for e in manifest["full"]]
    entries += [dict(e, form="chibi") for e in chibi["frames"]]
    if only:
        wanted = set(only)
        unknown = wanted - {e["name"] for e in entries}
        if unknown:
            raise SystemExit(f"unknown sprite(s): {', '.join(sorted(unknown))}")
        entries = [e for e in entries if e["name"] in wanted]

    jobs = []
    for e in entries:
        if e["form"] == "chibi":
            scene = f"{chibi['prefix']}, {e['scene']}, {chibi['background']}"
            strengths = denoise or e.get("denoise") or chibi["denoise"]
        else:
            scene = e["scene"]
            strengths = denoise or e.get("denoise") or d["denoise"]
        for dn in strengths:
            for i in range(n_seeds):
                jobs.append({
                    "name": e["name"],
                    "form": e["form"],
                    "scene": scene,
                    "denoise": float(dn),
                    "seed": seed_base + i,
                    "steps": d["steps"],
                    "cfg": d["cfg"],
                })
    return jobs


def plan_frame_jobs(manifest, only=None, priority=None, seeds=None, denoise=None,
                    seed_base=SEED_BASE):
    """One job per animation frame (x denoise x seed), named `<clip>_NN_cut`.

    Every frame is rendered off the same source still, and all frames of a clip share
    their seeds, so a clip reads as one sequence rather than N unrelated renders.
    """
    d, f, chibi = manifest["defaults"], manifest["frames"], manifest["chibi"]
    clips = f["clips"]
    if priority:
        clips = [c for c in clips if c["priority"] <= priority]
    if only:
        wanted = set(only)
        unknown = wanted - {c["clip"] for c in f["clips"]}
        if unknown:
            raise SystemExit(f"unknown clip(s): {', '.join(sorted(unknown))}")
        clips = [c for c in clips if c["clip"] in wanted]
    jobs = []
    for c in clips:
        for n, pose in enumerate(c["poses"], 1):
            scene = f"{chibi['prefix']}, {pose}, {f['suffix']}, {chibi['background']}"
            for dn in denoise or f["denoise"]:
                for i in range(seeds or f["seeds"]):
                    jobs.append({
                        "name": f"{c['clip']}_{n:02d}_cut",
                        "source": f["source"],
                        "form": "chibi",
                        "scene": scene,
                        "denoise": float(dn),
                        "seed": seed_base + i,
                        "steps": d["steps"],
                        "cfg": d["cfg"],
                    })
    return jobs


def build_graph(job, image_name, positive, negative, prefix,
                model=DEFAULT_MODEL, lora=DEFAULT_LORA, size=None, bg_rgb=None):
    """ComfyUI API graph for one img2img render.

    Full sprites: LoadImage -> VAEEncode -> KSampler at partial denoise.
    Chibi cutouts: the transparent source is first laid over a flat background colour
    (LoadImage's MASK is 1 - alpha, so it is inverted to select her), rendered at 2x
    because SDXL is poor at 512 px, then scaled back so the pet's frame size is kept.
    """
    g = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}},
        "2": {"class_type": "LoraLoader", "inputs": {
            "model": ["1", 0], "clip": ["1", 1], "lora_name": lora,
            "strength_model": LORA_STRENGTH, "strength_clip": LORA_STRENGTH}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 1], "text": positive}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 1], "text": negative}},
        "10": {"class_type": "LoadImage", "inputs": {"image": image_name}},
    }
    pixels = ["10", 0]
    if job["form"] == "chibi":
        w, h = size
        r, gr, b = bg_rgb
        g["11"] = {"class_type": "EmptyImage", "inputs": {
            "width": w, "height": h, "batch_size": 1, "color": (r << 16) | (gr << 8) | b}}
        g["12"] = {"class_type": "InvertMask", "inputs": {"mask": ["10", 1]}}
        g["13"] = {"class_type": "ImageCompositeMasked", "inputs": {
            "destination": ["11", 0], "source": ["10", 0], "x": 0, "y": 0,
            "resize_source": False, "mask": ["12", 0]}}
        g["14"] = {"class_type": "ImageScale", "inputs": {
            "image": ["13", 0], "upscale_method": "lanczos",
            "width": w * 2, "height": h * 2, "crop": "disabled"}}
        pixels = ["14", 0]
    g["20"] = {"class_type": "VAEEncode", "inputs": {"pixels": pixels, "vae": ["1", 2]}}
    g["21"] = {"class_type": "KSampler", "inputs": {
        "model": ["2", 0], "positive": ["3", 0], "negative": ["4", 0],
        "latent_image": ["20", 0], "seed": job["seed"], "steps": job["steps"],
        "cfg": job["cfg"], "sampler_name": "dpmpp_2m", "scheduler": "karras",
        "denoise": job["denoise"]}}
    g["22"] = {"class_type": "VAEDecode", "inputs": {"samples": ["21", 0], "vae": ["1", 2]}}
    out = ["22", 0]
    if job["form"] == "chibi":
        w, h = size
        g["23"] = {"class_type": "ImageScale", "inputs": {
            "image": out, "upscale_method": "lanczos",
            "width": w, "height": h, "crop": "disabled"}}
        out = ["23", 0]
    g["30"] = {"class_type": "SaveImage", "inputs": {"images": out, "filename_prefix": prefix}}
    return g


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


class Comfy:
    def __init__(self, base):
        self.base = base.rstrip("/")

    def _get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=30) as r:
            return json.loads(r.read())

    def preflight(self, model, lora):
        """-> list of problems; empty means ready."""
        try:
            self._get("/system_stats")
        except (urllib.error.URLError, OSError) as e:
            return [f"ComfyUI not answering at {self.base} ({e}) — start it first"]
        problems = []
        for node, field, want in (("CheckpointLoaderSimple", "ckpt_name", model),
                                  ("LoraLoader", "lora_name", lora)):
            try:
                info = self._get(f"/object_info/{node}")
                choices = info[node]["input"]["required"][field][0]
            except (KeyError, IndexError, TypeError, urllib.error.URLError, OSError):
                continue  # can't tell; let the render itself fail loudly
            if want not in choices:
                problems.append(f"{want} is not in ComfyUI's {field} list")
        return problems

    def upload(self, path):
        """Upload a source sprite; -> the name ComfyUI stored it under."""
        boundary = uuid.uuid4().hex
        data = Path(path).read_bytes()
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="image"; filename="{Path(path).name}"\r\n'.encode(),
            b"Content-Type: image/png\r\n\r\n", data, b"\r\n",
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="subfolder"\r\n\r\naster-regen\r\n',
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n',
            f"--{boundary}--\r\n".encode(),
        ])
        req = urllib.request.Request(
            self.base + "/upload/image", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read())
        sub = res.get("subfolder") or ""
        return f"{sub}/{res['name']}" if sub else res["name"]

    def queue(self, graph):
        body = json.dumps({"prompt": graph, "client_id": "aster-regen"}).encode()
        req = urllib.request.Request(self.base + "/prompt", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())["prompt_id"]
        except urllib.error.HTTPError as e:
            raise SystemExit(f"ComfyUI rejected the graph: {e.read().decode(errors='replace')[:800]}")

    def wait(self, prompt_id, timeout=900, poll=2.0):
        """-> list of saved filenames once the prompt finishes."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            hist = self._get(f"/history/{prompt_id}")
            entry = hist.get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(f"render failed: {status.get('messages')}")
                files = []
                for out in entry.get("outputs", {}).values():
                    for img in out.get("images", []):
                        sub = img.get("subfolder")
                        files.append(f"{sub}/{img['filename']}" if sub else img["filename"])
                if files:
                    return files
            time.sleep(poll)
        raise TimeoutError(f"prompt {prompt_id} did not finish in {timeout}s")


def find_sprites(given):
    candidates = [given] if given else SPRITE_DIRS
    for c in candidates:
        if c and Path(c).is_dir():
            return Path(c)
    tried = "\n  ".join(candidates)
    raise SystemExit(f"sprite folder not found; pass --sprites. Tried:\n  {tried}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sprites", help="folder holding her current sprites (Aster repo's sprites/)")
    ap.add_argument("--only", nargs="+", metavar="NAME", help="just these sprites, e.g. happy wave_02_cut")
    ap.add_argument("--seeds", type=int, help="seeds per denoise (default from sprites.json)")
    ap.add_argument("--seed-base", type=int, default=SEED_BASE)
    ap.add_argument("--denoise", type=float, nargs="+", help="override every sprite's denoise list")
    ap.add_argument("--comfy", default=DEFAULT_COMFY)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--lora", default=DEFAULT_LORA)
    ap.add_argument("--frames", action="store_true",
                    help="render the pet's multi-frame animations instead of the 13 sprites")
    ap.add_argument("--priority", type=int, choices=(1, 2, 3, 4),
                    help="with --frames: only clips at this priority or more urgent")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, touch nothing")
    args = ap.parse_args(argv)

    manifest = load_manifest()
    base = read_prompt(CHARACTERS / "aster-prompt.txt")
    negative = read_prompt(CHARACTERS / "aster-negative.txt")
    if args.frames:
        jobs = plan_frame_jobs(manifest, args.only, args.priority, args.seeds, args.denoise,
                               args.seed_base)
    else:
        jobs = plan_jobs(manifest, args.only, args.seeds, args.denoise, args.seed_base)
    stamp = time.strftime("%Y%m%d-%H%M")
    bg = manifest["chibi"]["background_rgb"]

    if args.dry_run:
        for j in jobs:
            print(f"{j['name']:<12} {j['form']:<5} denoise {j['denoise']:.2f}  seed {j['seed']}")
        print(f"\n{len(jobs)} renders. Positive for the first:\n\n{base}, {jobs[0]['scene']}"
              if jobs else "nothing to do")
        return 0

    sprites = find_sprites(args.sprites)
    comfy = Comfy(args.comfy)
    problems = comfy.preflight(args.model, args.lora)
    if problems:
        print("not ready:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2

    uploaded, missing, done = {}, set(), []
    for n, j in enumerate(jobs, 1):
        source = j.get("source", j["name"])
        src = sprites / f"{source}.png"
        if not src.is_file():
            if source not in missing:
                missing.add(source)
                print(f"skip {j['name']}: {src} missing", file=sys.stderr)
            continue
        if source not in uploaded:
            uploaded[source] = comfy.upload(src)
        prefix = f"aster/regen-{stamp}/{j['name']}_d{round(j['denoise'] * 100)}_s{j['seed']}"
        graph = build_graph(j, uploaded[source], f"{base}, {j['scene']}", negative, prefix,
                            args.model, args.lora,
                            size=png_size(src) if j["form"] == "chibi" else None, bg_rgb=bg)
        pid = comfy.queue(graph)
        files = comfy.wait(pid)
        done.extend(files)
        print(f"[{n}/{len(jobs)}] {j['name']} d{j['denoise']:.2f} s{j['seed']} -> {files[0]}")

    print(f"\n{len(done)} renders in ComfyUI's output folder, aster/regen-{stamp}/")
    print("Pick winners against the checklist in characters/sprite-regen/README.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
