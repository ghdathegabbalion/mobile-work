"""Render a fixed prompt x seed grid with each LoRA (v1 vs v2) on the PC's ComfyUI.

    python compare.py --dry-run                                  # the plan + one graph, no network
    python compare.py                                            # v1 vs v2, every prompt, 3 seeds
    python compare.py --loras v1=aster-illustrious-v1.safetensors e8=aster-illustrious-v2-000008.safetensors v2=aster-illustrious-v2.safetensors
    python compare.py --loras none=none v2=aster-illustrious-v2.safetensors   # base model as control

Prompts come from eval_prompts.txt, positive/negative from characters/aster-prompt.txt and
aster-negative.txt (comment lines stripped, as regen.py does). Every LoRA gets the same
prompt, seed, size, steps and CFG, so the only variable is the LoRA.

Renders land in ComfyUI's output folder as ASTER_compare-<stamp>_<label>_<prompt>_s<seed>.
The script also writes compare-<stamp>.html (the side-by-side grid) and scores-<stamp>.csv
(a blank scoring sheet, one row per image) into --out. Score with compare.md.

Reuses sprite-regen/regen.py's ComfyUI client (preflight, queue, wait).
"""

import argparse
import csv
import html
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHARACTERS = HERE.parent
sys.path.insert(0, str(CHARACTERS / "sprite-regen"))
import regen  # noqa: E402
from caption import load_eval_prompts, load_json  # noqa: E402

DEFAULT_LORAS = ["v1=aster-illustrious-v1.safetensors", "v2=aster-illustrious-v2.safetensors"]
SEED_BASE = 20260926
LORA_STRENGTH = 0.8   # v1's working value; the comparison is only fair at one strength
FULL_SIZE = (832, 1216)
CHIBI_SIZE = (1024, 1024)
LABEL_RE = re.compile(r"^[A-Za-z0-9]+$")  # no underscores: they delimit the filename


def parse_loras(specs):
    """['v1=file.safetensors', 'none=none'] -> [(label, file or None)]."""
    out = []
    for s in specs:
        label, _, name = s.partition("=")
        if not LABEL_RE.match(label) or not name:
            raise SystemExit(f"--loras entries are LABEL=FILE with a letters/digits label: {s!r}")
        out.append((label, None if name.lower() == "none" else name))
    if len({l for l, _ in out}) != len(out):
        raise SystemExit("--loras labels must be unique")
    return out


def plan(prompts, loras, seeds, seed_base=SEED_BASE, only=None):
    """One job per (prompt, seed, lora). LoRAs vary fastest, so an interrupted run still
    leaves complete side-by-side pairs."""
    if only:
        unknown = set(only) - {p["id"] for p in prompts}
        if unknown:
            raise SystemExit(f"unknown prompt id(s): {', '.join(sorted(unknown))}")
        prompts = [p for p in prompts if p["id"] in only]
    jobs = []
    for p in prompts:
        for i in range(seeds):
            for label, lora in loras:
                jobs.append({"prompt": p, "seed": seed_base + i, "label": label, "lora": lora,
                             "size": CHIBI_SIZE if "chibi" in p["text"] else FULL_SIZE})
    return jobs


def positive_for(p, base, trigger):
    return f"{base}, {p['text']}" if p["mode"] == "canon" else f"{trigger}, {p['text']}"


def build_graph(job, positive, negative, prefix, model=regen.DEFAULT_MODEL,
                strength=LORA_STRENGTH, steps=30, cfg=6.5):
    """txt2img: checkpoint -> [LoRA] -> encode -> empty latent -> KSampler -> decode -> save."""
    g = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}}}
    m, c = ["1", 0], ["1", 1]
    if job["lora"]:
        g["2"] = {"class_type": "LoraLoader", "inputs": {
            "model": m, "clip": c, "lora_name": job["lora"],
            "strength_model": strength, "strength_clip": strength}}
        m, c = ["2", 0], ["2", 1]
    w, h = job["size"]
    g["3"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": c, "text": positive}}
    g["4"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": c, "text": negative}}
    g["5"] = {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}
    g["21"] = {"class_type": "KSampler", "inputs": {
        "model": m, "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["5", 0],
        "seed": job["seed"], "steps": steps, "cfg": cfg, "sampler_name": "dpmpp_2m",
        "scheduler": "karras", "denoise": 1.0}}
    g["22"] = {"class_type": "VAEDecode", "inputs": {"samples": ["21", 0], "vae": ["1", 2]}}
    g["30"] = {"class_type": "SaveImage", "inputs": {"images": ["22", 0], "filename_prefix": prefix}}
    return g


def prefix_for(stamp, job):
    return f"ASTER_compare-{stamp}_{job['label']}_{job['prompt']['id']}_s{job['seed']}"


def write_report(out, stamp, jobs, files, comfy_output, checklist):
    out.mkdir(parents=True, exist_ok=True)
    labels = list(dict.fromkeys(j["label"] for j in jobs))
    rows = {}
    for j, f in zip(jobs, files):
        rows.setdefault((j["prompt"]["id"], j["seed"]), {})[j["label"]] = f
    cells = []
    for (pid, seed), by in rows.items():
        tds = "".join(
            f'<td><a href="{html.escape((comfy_output / by[l]).as_uri())}" target="_blank">'
            f'<img loading="lazy" src="{html.escape((comfy_output / by[l]).as_uri())}"></a></td>'
            if by.get(l) else "<td>-</td>" for l in labels)
        cells.append(f"<tr><th>{html.escape(pid)}<br>s{seed}</th>{tds}</tr>")
    head = "".join(f"<th>{html.escape(l)}</th>" for l in labels)
    page = (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            f"<title>Aster LoRA compare {stamp}</title><style>body{{font:14px system-ui;margin:16px}}"
            f"img{{width:100%;max-width:360px}}td,th{{vertical-align:top;padding:4px}}</style>"
            f"<h1>Aster LoRA compare {stamp}</h1><p>Score with compare.md; fill scores-{stamp}.csv."
            f"</p><table><tr><th></th>{head}</tr>{''.join(cells)}</table>")
    (out / f"compare-{stamp}.html").write_text(page, encoding="utf-8")
    with open(out / f"scores-{stamp}.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["file", "lora", "prompt", "seed"] + [c["id"] for c in checklist] + ["notes"])
        for j, f in zip(jobs, files):
            wr.writerow([f, j["label"], j["prompt"]["id"], j["seed"]] + [""] * len(checklist) + [""])
    return out / f"compare-{stamp}.html"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--loras", nargs="+", default=DEFAULT_LORAS, metavar="LABEL=FILE",
                    help="LoRAs to compare; FILE 'none' renders the bare checkpoint")
    ap.add_argument("--only", nargs="+", metavar="ID", help="just these prompt ids")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--seed-base", type=int, default=SEED_BASE)
    ap.add_argument("--strength", type=float, default=LORA_STRENGTH)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--cfg", type=float, default=6.5)
    ap.add_argument("--model", default=regen.DEFAULT_MODEL)
    ap.add_argument("--comfy", default=regen.DEFAULT_COMFY)
    ap.add_argument("--comfy-output", default=str(Path.home() / "Documents" / "ComfyUI" / "output"),
                    help="ComfyUI's output folder, for the HTML grid's image links")
    ap.add_argument("--out", default=str(Path.home() / "lora-v2" / "compare"),
                    help="where compare-<stamp>.html and scores-<stamp>.csv go")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and one graph; no network")
    args = ap.parse_args(argv)

    canon = load_json(HERE / "canon_tags.json")
    base = regen.read_prompt(CHARACTERS / "aster-prompt.txt")
    negative = regen.read_prompt(CHARACTERS / "aster-negative.txt")
    loras = parse_loras(args.loras)
    jobs = plan(load_eval_prompts(), loras, args.seeds, args.seed_base, args.only)
    stamp = time.strftime("%Y%m%d-%H%M")

    if args.dry_run:
        for j in jobs:
            print(f"{j['prompt']['id']:<12} s{j['seed']}  {j['label']:<4} {j['lora'] or '(no LoRA)'}")
        if jobs:
            j = jobs[0]
            g = build_graph(j, positive_for(j["prompt"], base, canon["trigger"]), negative,
                            prefix_for(stamp, j), args.model, args.strength, args.steps, args.cfg)
            print(f"\n{len(jobs)} renders. First graph:\n{json.dumps(g, indent=1)}")
        return 0

    comfy = regen.Comfy(args.comfy)
    wanted = [lora for _, lora in loras if lora]
    problems = []
    # An all-"none" run still checks ComfyUI and the checkpoint; the LoRA verdict is ignored.
    for lora in wanted or [regen.DEFAULT_LORA]:
        for p in comfy.preflight(args.model, lora):
            if p not in problems and (wanted or lora not in p):
                problems.append(p)
    if problems:
        print("not ready:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2

    files = []
    for n, j in enumerate(jobs, 1):
        g = build_graph(j, positive_for(j["prompt"], base, canon["trigger"]), negative,
                        prefix_for(stamp, j), args.model, args.strength, args.steps, args.cfg)
        got = comfy.wait(comfy.queue(g))
        files.append(got[0])
        print(f"[{n}/{len(jobs)}] {j['prompt']['id']} s{j['seed']} {j['label']} -> {got[0]}")
    page = write_report(Path(args.out), stamp, jobs, files, Path(args.comfy_output),
                        canon["checklist"])
    print(f"\ngrid: {page}\nScore it with characters/lora-v2/compare.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
