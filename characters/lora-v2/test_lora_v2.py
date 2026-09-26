"""Tests for the LoRA v2 prep kit. Stdlib unittest; no GPU, no network, no ComfyUI.

    python -m unittest characters/lora-v2/test_lora_v2.py
"""

import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import caption  # noqa: E402
import compare  # noqa: E402
import curate   # noqa: E402

CANON = json.loads((HERE / "canon_tags.json").read_text(encoding="utf-8"))
SPRITES = json.loads((HERE.parent / "sprite-regen" / "sprites.json").read_text(encoding="utf-8"))
EVALS = caption.load_eval_prompts()
ASTER_MD = (HERE.parent / "aster.md").read_text(encoding="utf-8")

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None


def norm(text):
    """Markdown -> comparable plain text: no bold markers, single spaces."""
    return re.sub(r"\s+", " ", text.replace("**", "").replace("*", ""))


def locked_section():
    m = re.search(r"## Locked traits.*?\n(.*?)\n## ", ASTER_MD, re.S)
    return m.group(1)


def all_locked_tags():
    return [t for g in CANON["locked"] if not g.get("when") for t in g["tags"]]


# ------------------------------------------------------------------ captions

class CaptionAssembly(unittest.TestCase):
    def test_trigger_first_then_locked_then_variable(self):
        tags = caption.assemble(CANON, "full", ["full body", "waving", "beach at sunset"])
        self.assertEqual(tags[0], "asterfen")
        self.assertEqual(tags.count("asterfen"), 1)
        locked = all_locked_tags()
        self.assertEqual(tags[1:1 + len(locked)], locked)
        self.assertEqual(tags[-3:], ["full body", "waving", "beach at sunset"])

    def test_chibi_form_tags_follow_trigger(self):
        tags = caption.assemble(CANON, "chibi", ["standing"])
        self.assertEqual(tags[:3], ["asterfen", "chibi", "super deformed"])
        for t in all_locked_tags():  # the chibi carries every locked trait
            self.assertIn(t, tags)

    def test_required_canon_tags_present(self):
        tags = caption.assemble(CANON, "full", [])
        for t in ["single tail", "fox fur tail base", "marigold tail band", "ink-violet tentacle tail",
                  "blonde bob", "blunt bangs", "amber eyes", "aster flower at left ear",
                  "brown leather hip pouch", "gold crescent moon", "ink-dipped paws",
                  "white knitted scarf"]:
            self.assertIn(t, tags)

    def test_sweater_tag_only_with_a_sweater(self):
        self.assertNotIn("lavender sweater", caption.assemble(CANON, "full", ["white sundress"]))
        self.assertIn("lavender sweater", caption.assemble(CANON, "full", ["oversized sweater"]))

    def test_banned_phrases_dropped_from_variable_tags(self):
        dropped = []
        tags = caption.assemble(CANON, "full",
                                ["many arms for parallel work", "big ears for listening",
                                 "warm above", "deep below", "two tails", "fox tail",
                                 "brown eyes", "coral tail", "waving"], log=dropped.append)
        text = ", ".join(tags)
        for s in CANON["banned_substrings"]:
            self.assertNotIn(s, text)
        self.assertNotIn("fox tail", tags)
        self.assertIn("waving", tags)
        self.assertEqual(len(dropped), 8)

    def test_locked_tags_themselves_are_not_banned(self):
        self.assertEqual(caption.banned_hits(all_locked_tags(), CANON), [])

    def test_no_persona_metaphor_anywhere_in_generated_captions(self):
        for e in SPRITES["full"] + SPRITES["chibi"]["frames"]:
            _, var = caption.scene_from_name(e["name"], SPRITES, EVALS)
            text = ", ".join(caption.assemble(CANON, "full", var))
            self.assertNotIn("many arms", text)
            self.assertNotIn("parallel work", text)

    def test_drop_hidden(self):
        checks = {"one_tail": "na", "marigold_band": "na"}
        tags = caption.assemble(CANON, "full", ["portrait"], checks, drop_hidden=True)
        self.assertNotIn("single tail", tags)
        self.assertNotIn("marigold tail band", tags)
        self.assertIn("amber eyes", tags)
        self.assertIn("single tail", caption.assemble(CANON, "full", ["portrait"], checks))

    def test_weights_and_brackets_stripped(self):
        self.assertEqual(caption.split_tags("(plain flat mint green background:1.3), simple background"),
                         ["plain flat mint green background", "simple background"])

    def test_scene_from_filenames(self):
        form, tags = caption.scene_from_name("ASTER_regen-20260925-1200_happy_d55_s20260925_00001_",
                                             SPRITES, EVALS)
        self.assertEqual(form, "full")
        self.assertIn("jumping", tags)
        form, tags = caption.scene_from_name("ASTER_regen-20260925-1200_wave_02_cut_d55_s20260925_00001_",
                                             SPRITES, EVALS)
        self.assertEqual(form, "chibi")
        self.assertIn("simple background", tags)
        form, tags = caption.scene_from_name("dance_03_cut", SPRITES, EVALS)
        self.assertEqual(form, "chibi")
        self.assertTrue(tags)
        form, tags = caption.scene_from_name("ASTER_compare-20260926-0900_v1_back_tail_s20260926_00001_",
                                             SPRITES, EVALS)
        self.assertIn("from behind", tags)
        self.assertEqual(caption.scene_from_name("mystery", SPRITES, EVALS), (None, []))

    def test_caption_dataset_writes_files(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "shy.png").write_bytes(b"x")
            (d / "idle_cut.png").write_bytes(b"x")
            (d / "aster-ref.png").write_bytes(b"x")
            (d / "_meta.json").write_text(json.dumps({
                "idle_cut.png": {"source_stem": "idle_cut", "form": "chibi", "shot": "full_front",
                                 "flattened": True, "checks": {}}}))
            overrides = json.loads((HERE / "overrides.json").read_text(encoding="utf-8"))
            res = caption.caption_dataset(d, CANON, SPRITES, EVALS, overrides, log=lambda *_: None)
            self.assertEqual(set(res), {"shy.png", "idle_cut.png", "aster-ref.png"})
            for name, cap in res.items():
                self.assertTrue(cap.startswith("asterfen, "), name)
                self.assertEqual((d / name).with_suffix(".txt").read_text(encoding="utf-8").strip(), cap)
            self.assertIn("white background", res["idle_cut.png"])
            self.assertNotIn("green background", res["idle_cut.png"])
            self.assertIn("chibi", res["idle_cut.png"].split(", ")[1])
            self.assertIn("gradient background", res["aster-ref.png"])
            self.assertIn("lavender sweater", res["shy.png"])

    def test_keep_tokens_matches_default_shuffle_keep(self):
        if tomllib is None:
            self.skipTest("tomllib needs Python 3.11+")
        kt = caption.read_keep_tokens(HERE / "train_config" / "dataset.toml")
        self.assertEqual(kt, 1)
        with redirect_stderr(io.StringIO()):
            rc = caption.main(["--dataset", ".", "--config", str(HERE / "train_config" / "dataset.toml"),
                               "--shuffle-keep", "2"])
        self.assertEqual(rc, 2)


# ------------------------------------------------------------------ canon consistency

class CanonConsistency(unittest.TestCase):
    def test_trigger_matches_prompt_file(self):
        first = next(l for l in (HERE.parent / "aster-prompt.txt").read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.startswith("#"))
        self.assertEqual(first.split(",")[0].strip(), CANON["trigger"])
        self.assertIn(f"trigger word:** `{CANON['trigger']}`", ASTER_MD.lower())

    def test_every_locked_evidence_is_in_the_locked_section(self):
        section = norm(locked_section()).lower()
        for g in CANON["locked"]:
            for ev in g["evidence"]:
                self.assertIn(norm(ev).lower(), section, f"{g['trait']}: '{ev}' not in aster.md Locked traits")

    def test_every_locked_trait_in_aster_md_is_covered(self):
        labels = re.findall(r"^- \*\*([^*:.]+?)(?: — [^*]*)?[:.]?\*\*", locked_section(), re.M)
        self.assertGreaterEqual(len(labels), 12)
        covered = {g["trait"] for g in CANON["locked"]}
        for label in labels:
            self.assertIn(label.strip(), covered, f"aster.md locked trait '{label}' has no canon_tags entry")

    def test_exclusion_evidence_in_aster_md(self):
        text = norm(ASTER_MD).lower()
        for x in CANON["exclude"]:
            self.assertIn(norm(x["evidence"]).lower(), text, x["id"])

    def test_required_exclusions_and_checks(self):
        ex = {x["id"] for x in CANON["exclude"]}
        self.assertTrue({"two_tails", "brown_eyes", "coral_band", "white_sweater", "missing_pouch"} <= ex)
        checks = {c["id"] for c in CANON["checklist"]}
        for g in CANON["locked"]:
            if "check" in g:
                self.assertIn(g["check"], checks)

    def test_readme_lists_every_locked_tag(self):
        readme = re.sub(r"\s+", " ", (HERE / "README.md").read_text(encoding="utf-8"))
        for t in all_locked_tags():
            self.assertIn(t, readme)

    def test_aster_md_points_at_lora_v2(self):
        self.assertIn("lora-v2/", ASTER_MD)

    def test_left_ear_not_right(self):
        self.assertIn("base of her left ear", ASTER_MD)
        self.assertIn("aster flower at left ear", all_locked_tags())


# ------------------------------------------------------------------ curate

def synth(w, h, fn, alpha=None):
    """RGB(A) raster from fn(x, y) -> (r, g, b)."""
    ch = 4 if alpha is not None else 3
    data = bytearray()
    for y in range(h):
        for x in range(w):
            data += bytes(fn(x, y))
            if alpha is not None:
                data.append(alpha(x, y))
    return curate.Raster(w, h, ch, data)


def gradient(x, y):
    return (min(255, x * 4), min(255, y * 3), 128)


def gradient_tweaked(x, y):
    r, g, b = gradient(x, y)
    return (min(255, r + 3), g, b if (x, y) != (5, 5) else 0)


def checker(x, y):
    v = 255 if ((x // 8) + (y // 8)) % 2 else 0
    return (v, 255 - v, v)


class CurateDedupe(unittest.TestCase):
    def _hashes_via_png(self, use_pil):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(curate, "HAVE_PIL", use_pil):
            paths = []
            for i, fn in enumerate([gradient, gradient_tweaked, checker]):
                p = Path(d) / f"img{i}.png"
                curate.png_write(p, synth(64, 48, fn))
                paths.append(p)
            return [curate.dhash(curate.load_raster(p)) for p in paths]

    def test_dedupe_stdlib(self):
        h = self._hashes_via_png(False)
        self.assertEqual(curate.group_duplicates(h), [0, 0, 1])

    @unittest.skipUnless(curate.HAVE_PIL, "Pillow not installed")
    def test_dedupe_pillow(self):
        h = self._hashes_via_png(True)
        self.assertEqual(curate.group_duplicates(h), [0, 0, 1])

    def test_unreadable_never_groups(self):
        self.assertEqual(curate.group_duplicates([None, None, 5]), [0, 1, 2])

    def test_png_roundtrip_rgba(self):
        r = synth(10, 7, gradient, alpha=lambda x, y: 0 if x < 3 else 255)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.png"
            curate.png_write(p, r)
            back = curate.png_read(p)
        self.assertEqual((back.w, back.h, bytes(back.data)), (10, 7, bytes(r.data)))
        flat, had = curate.flatten(back)
        self.assertTrue(had)
        self.assertEqual(tuple(flat.data[:3]), curate.FLATTEN_BG)

    def test_scan_marks_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.mkdir()
            curate.png_write(src / "ASTER_regen-20260925-1200_idle_d45_s1_00001_.png", synth(64, 48, gradient))
            curate.png_write(src / "ASTER_regen-20260925-1200_idle_d45_s2_00001_.png", synth(64, 48, gradient_tweaked))
            curate.png_write(src / "wave_02_cut.png", synth(64, 48, checker))
            curate.png_write(src / "skip.png", synth(8, 8, checker))
            cands = curate.scan([f"{src}::*_*"], Path(d) / "work", log=lambda *_: None)
            self.assertEqual([c["name"] for c in cands][0][:11], "ASTER_regen")
            self.assertEqual(len(cands), 3)
            self.assertIsNone(cands[0]["dup_of"])
            self.assertEqual(cands[1]["dup_of"], cands[0]["id"])
            self.assertIsNone(cands[2]["dup_of"])
            self.assertEqual(cands[2]["form"], "chibi")
            page = curate.write_sheet(cands, Path(d) / "work", CANON)
            text = page.read_text(encoding="utf-8")
            self.assertIn("one_tail", text)
            self.assertNotIn("__DATA__", text)


class CurateBuild(unittest.TestCase):
    def good(self, path, **kw):
        e = {"id": "c001", "path": str(path), "keep": True, "form": "full", "shot": "full_front",
             "checks": {c["id"]: "pass" for c in CANON["checklist"]}, "exclude": [], "dup_group": 0}
        e["checks"]["lavender_sweater"] = "na"
        e.update(kw)
        return e

    def test_rules(self):
        p = curate.entry_problems
        self.assertEqual(p(self.good("x"), CANON), [])
        self.assertTrue(p(self.good("x", exclude=["two_tails"]), CANON))
        bad = self.good("x")
        bad["checks"]["amber_eyes"] = "fail"
        self.assertIn("fails: amber_eyes", p(bad, CANON))
        unscored = self.good("x")
        del unscored["checks"]["moon_pouch"]
        self.assertIn("not scored: moon_pouch", p(unscored, CANON))
        back = self.good("x", shot="back_view")
        back["checks"]["one_tail"] = "na"
        self.assertTrue(p(back, CANON))
        face = self.good("x", shot="upper_body")
        face["checks"]["one_tail"] = face["checks"]["marigold_band"] = "na"
        self.assertEqual(p(face, CANON), [])

    def test_bucket(self):
        self.assertEqual(curate.pick_bucket(848, 1264), (832, 1216))
        self.assertEqual(curate.pick_bucket(512, 512), (1024, 1024))
        self.assertEqual(curate.pick_bucket(1920, 1080), (1344, 768))

    def test_build_resizes_pads_and_dedupes(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(curate, "HAVE_PIL", False), \
                mock.patch.object(curate, "SDXL_BUCKETS", [(64, 64), (48, 64)]):
            d = Path(d)
            a, b, c = d / "a.png", d / "b.png", d / "c_cut.png"
            curate.png_write(a, synth(30, 40, gradient))
            curate.png_write(b, synth(30, 40, gradient_tweaked))
            curate.png_write(c, synth(20, 20, checker, alpha=lambda x, y: 0 if x < 2 else 255))
            sel = {"images": [self.good(a, dup_group=0), self.good(b, id="c002", dup_group=0),
                              self.good(c, id="c003", form="chibi", dup_group=1),
                              self.good(d / "nope.png", id="c004", keep=False, dup_group=2),
                              self.good(d / "bad.png", id="c005", exclude=["coral_band"], dup_group=3)]}
            (d / "selection.json").write_text(json.dumps(sel))
            logs = []
            kept = curate.build(d / "selection.json", d / "ds", CANON, log=logs.append)
            self.assertEqual([Path(e["path"]).name for e in kept], ["a.png", "c_cut.png"])
            self.assertTrue(any("near-duplicate" in l for l in logs))
            self.assertTrue(any("coral_band" in l for l in logs))
            out = curate.png_read(d / "ds" / "a.png")
            self.assertEqual((out.w, out.h), (48, 64))
            out = curate.png_read(d / "ds" / "c_cut.png")
            self.assertEqual((out.w, out.h), (64, 64))
            meta = json.loads((d / "ds" / "_meta.json").read_text())
            self.assertTrue(meta["c_cut.png"]["flattened"])
            self.assertEqual(meta["c_cut.png"]["form"], "chibi")

    def test_resize_preserves_flat_colour(self):
        r = synth(10, 10, lambda x, y: (200, 100, 50))
        for w, h in ((5, 5), (23, 17)):
            out = curate.resize(r, w, h)
            self.assertEqual(set(zip(out.data[0::3], out.data[1::3], out.data[2::3])), {(200, 100, 50)})


# ------------------------------------------------------------------ train config

@unittest.skipIf(tomllib is None, "tomllib needs Python 3.11+")
class TrainConfig(unittest.TestCase):
    def load(self, name):
        with open(HERE / "train_config" / name, "rb") as f:
            return tomllib.load(f)

    def flat(self, cfg):  # sd-scripts flattens one level of sections
        out = {}
        for k, v in cfg.items():
            out.update(v if isinstance(v, dict) else {k: v})
        return out

    def test_training_toml(self):
        c = self.flat(self.load("aster-v2.toml"))
        self.assertEqual(c["output_name"], "aster-illustrious-v2")
        self.assertEqual(c["network_module"], "networks.lora")
        self.assertLessEqual(c["network_alpha"], c["network_dim"])
        self.assertTrue(c["cache_latents"] and c["cache_latents_to_disk"])
        self.assertTrue(c["gradient_checkpointing"])
        self.assertLessEqual(c["max_data_loader_n_workers"], 1)
        self.assertEqual(c["max_token_length"], 225)
        self.assertGreater(c["min_snr_gamma"], 0)
        self.assertGreater(c["noise_offset"], 0)
        self.assertEqual(c["max_train_epochs"] % c["save_every_n_epochs"], 0)
        self.assertNotIn("pretrained_model_name_or_path", c)  # paths come from train.ps1

    def test_dataset_toml(self):
        cfg = self.load("dataset.toml")
        g = cfg["general"]
        self.assertFalse(g["flip_aug"])  # the bloom is on her LEFT ear
        self.assertTrue(g["shuffle_caption"])
        self.assertEqual(g["keep_tokens"], 1)
        sub = cfg["datasets"][0]["subsets"][0]
        self.assertEqual(sub["image_dir"], "__DATASET_DIR__")
        self.assertIn("num_repeats", sub)

    def test_train_ps1_substitutes_placeholder(self):
        ps = (HERE / "train_config" / "train.ps1").read_text(encoding="utf-8")
        self.assertIn("__DATASET_DIR__", ps)
        self.assertIn("num_repeats = \\d+", ps)
        self.assertIn("UTF8Encoding $false", ps)

    def test_sample_prompts(self):
        lines = [l for l in (HERE / "train_config" / "sample_prompts.txt").read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#")]
        self.assertGreaterEqual(len(lines), 6)
        for l in lines:
            self.assertTrue(l.startswith("asterfen, "))
            self.assertIn("--d ", l)
            self.assertNotIn("many arms", l.split("--n")[0])
        self.assertTrue(any("from behind" in l for l in lines))
        self.assertTrue(any("chibi" in l for l in lines))


# ------------------------------------------------------------------ compare

class Compare(unittest.TestCase):
    def test_eval_prompts_cover_back_view_and_chibi(self):
        ids = {p["id"] for p in EVALS}
        self.assertTrue({"back_tail", "chibi", "face", "paws_sit", "sweater"} <= ids)
        for p in EVALS:
            self.assertRegex(p["id"], r"^[a-z0-9_]+$")
            if p["mode"] == "bare":  # bare prompts must not name canon traits
                for t in ["marigold", "amber", "aster flower", "pouch", "ink-dipped", "tentacle"]:
                    self.assertNotIn(t, p["text"], p["id"])

    def test_plan_shape(self):
        loras = compare.parse_loras(compare.DEFAULT_LORAS)
        jobs = compare.plan(EVALS, loras, seeds=3)
        self.assertEqual(len(jobs), len(EVALS) * 3 * 2)
        self.assertEqual([j["label"] for j in jobs[:2]], ["v1", "v2"])
        self.assertEqual(jobs[0]["seed"], jobs[1]["seed"])

    def test_graph_shape(self):
        job = compare.plan(EVALS, compare.parse_loras(["v2=aster-illustrious-v2.safetensors"]), 1,
                           only=["back_tail"])[0]
        g = compare.build_graph(job, "asterfen, x", "neg", "ASTER_compare-x_v2_back_tail_s1")
        classes = {v["class_type"] for v in g.values()}
        self.assertEqual(classes, {"CheckpointLoaderSimple", "LoraLoader", "CLIPTextEncode",
                                   "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage"})
        self.assertEqual(g["2"]["inputs"]["lora_name"], "aster-illustrious-v2.safetensors")
        self.assertEqual(g["21"]["inputs"]["model"], ["2", 0])
        self.assertEqual(g["3"]["inputs"]["clip"], ["2", 1])
        self.assertEqual(g["21"]["inputs"]["denoise"], 1.0)
        # every link points at a node that exists
        for node in g.values():
            for v in node["inputs"].values():
                if isinstance(v, list):
                    self.assertIn(v[0], g)

    def test_graph_without_lora(self):
        job = compare.plan(EVALS, compare.parse_loras(["none=none"]), 1, only=["chibi"])[0]
        g = compare.build_graph(job, "p", "n", "x")
        self.assertNotIn("2", g)
        self.assertEqual(g["21"]["inputs"]["model"], ["1", 0])
        self.assertEqual((g["5"]["inputs"]["width"], g["5"]["inputs"]["height"]), compare.CHIBI_SIZE)

    def test_positive_modes(self):
        bare = next(p for p in EVALS if p["mode"] == "bare")
        canon = next(p for p in EVALS if p["mode"] == "canon")
        self.assertEqual(compare.positive_for(bare, "BASE", "asterfen"), f"asterfen, {bare['text']}")
        self.assertTrue(compare.positive_for(canon, "BASE", "asterfen").startswith("BASE, "))

    def test_bad_labels_rejected(self):
        with self.assertRaises(SystemExit):
            compare.parse_loras(["v_1=x.safetensors"])

    def test_dry_run_touches_no_network(self):
        with mock.patch.object(compare.regen, "Comfy", side_effect=AssertionError("network")):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = compare.main(["--dry-run", "--seeds", "2"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn(f"{len(EVALS) * 2 * 2} renders", out)
        graph = json.loads(out[out.index("{"):])
        self.assertEqual(graph["30"]["class_type"], "SaveImage")
        self.assertTrue(graph["30"]["inputs"]["filename_prefix"].startswith("ASTER_compare-"))
        self.assertTrue(graph["3"]["inputs"]["text"].startswith("asterfen, "))

    def test_compare_filenames_round_trip_into_captions(self):
        job = compare.plan(EVALS, compare.parse_loras(["v1=a.safetensors"]), 1, only=["side_walk"])[0]
        stem = compare.prefix_for("20260926-0900", job) + "_00001_"
        _, tags = caption.scene_from_name(stem, SPRITES, EVALS)
        self.assertIn("from side", tags)

    def test_report(self):
        jobs = compare.plan(EVALS, compare.parse_loras(compare.DEFAULT_LORAS), 1, only=["face"])
        with tempfile.TemporaryDirectory() as d:
            page = compare.write_report(Path(d), "stamp", jobs, ["a.png", "b.png"], Path(d), CANON["checklist"])
            self.assertIn("a.png", page.read_text(encoding="utf-8"))
            csv_text = (Path(d) / "scores-stamp.csv").read_text(encoding="utf-8")
            self.assertIn("one_tail", csv_text.splitlines()[0])
            self.assertEqual(len(csv_text.strip().splitlines()), 3)


if __name__ == "__main__":
    unittest.main()
