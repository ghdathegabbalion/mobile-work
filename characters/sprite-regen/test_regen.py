"""Tests for regen.py against a stub ComfyUI. No GPU, no network.

    python -m unittest characters/sprite-regen/test_regen.py
"""

import json
import struct
import sys
import tempfile
import threading
import unittest
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import regen  # noqa: E402


def tiny_png(path, w, h):
    raw = b"".join(b"\x00" + b"\x00\x00\x00" * w for _ in range(h))

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    Path(path).write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b""))


class StubComfy(BaseHTTPRequestHandler):
    uploads, graphs = [], []
    loras = [regen.DEFAULT_LORA]

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/system_stats":
            return self._json({"system": {}})
        if path == "/object_info/LoraLoader":
            return self._json({"LoraLoader": {"input": {"required": {"lora_name": [self.loras]}}}})
        if path == "/object_info/CheckpointLoaderSimple":
            return self._json({"CheckpointLoaderSimple": {"input": {"required": {
                "ckpt_name": [[regen.DEFAULT_MODEL]]}}}})
        if path.startswith("/history/"):
            pid = path.rsplit("/", 1)[1]
            prefix = self.graphs[int(pid)]["30"]["inputs"]["filename_prefix"]
            return self._json({pid: {"status": {"status_str": "success"}, "outputs": {
                "30": {"images": [{"filename": prefix.rsplit("/", 1)[1] + "_00001_.png",
                                   "subfolder": prefix.rsplit("/", 1)[0]}]}}}})
        self._json({}, 404)

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        path = urlparse(self.path).path
        if path == "/upload/image":
            name = body.split(b'filename="', 1)[1].split(b'"', 1)[0].decode()
            self.uploads.append(name)
            return self._json({"name": name, "subfolder": "aster-regen", "type": "input"})
        if path == "/prompt":
            self.graphs.append(json.loads(body)["prompt"])
            return self._json({"prompt_id": str(len(self.graphs) - 1)})
        self._json({}, 404)


class RegenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), StubComfy)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        StubComfy.uploads.clear()
        StubComfy.graphs.clear()
        StubComfy.loras = [regen.DEFAULT_LORA]
        self.tmp = tempfile.TemporaryDirectory()
        self.sprites = Path(self.tmp.name)
        tiny_png(self.sprites / "happy.png", 896, 1152)
        tiny_png(self.sprites / "wave_02_cut.png", 512, 640)
        tiny_png(self.sprites / "wave_03_cut.png", 512, 640)

    def tearDown(self):
        self.tmp.cleanup()

    def run_regen(self, *extra):
        return regen.main(["--sprites", str(self.sprites), "--comfy", self.url, *extra])

    def test_prompt_comments_never_reach_the_encoder(self):
        text = regen.read_prompt(regen.CHARACTERS / "aster-prompt.txt")
        self.assertTrue(text.startswith("asterfen,"), "trigger word must stay first")
        self.assertNotIn("many arms", text)
        self.assertNotIn("#", text)
        self.assertNotIn("\n", text)
        self.assertNotIn("many arms for parallel",
                         regen.read_prompt(regen.CHARACTERS / "aster-negative.txt"))

    def test_manifest_covers_every_sprite_in_her_repo(self):
        names = [j["name"] for j in regen.plan_jobs(regen.load_manifest(), seeds=1)]
        self.assertEqual(sorted(set(names)), sorted([
            "idle", "wave", "happy", "dance", "think", "sleepy", "excited", "shy",
            "idle_cut", "think_cut", "sleepy_cut", "wave_02_cut", "wave_03_cut"]))

    def test_wave_frames_share_seeds_and_denoise(self):
        jobs = regen.plan_jobs(regen.load_manifest(), only=["wave_02_cut", "wave_03_cut"])
        a = [(j["denoise"], j["seed"]) for j in jobs if j["name"] == "wave_02_cut"]
        b = [(j["denoise"], j["seed"]) for j in jobs if j["name"] == "wave_03_cut"]
        self.assertEqual(a, b)

    def test_per_sprite_denoise_overrides_default(self):
        jobs = regen.plan_jobs(regen.load_manifest(), only=["happy"], seeds=1)
        self.assertEqual([j["denoise"] for j in jobs], [0.55, 0.62])

    def test_unknown_sprite_is_refused(self):
        with self.assertRaises(SystemExit):
            regen.plan_jobs(regen.load_manifest(), only=["nope"])

    def test_full_sprite_renders_img2img(self):
        self.assertEqual(self.run_regen("--only", "happy", "--seeds", "1"), 0)
        self.assertEqual(StubComfy.uploads, ["happy.png"])  # uploaded once, reused
        self.assertEqual(len(StubComfy.graphs), 2)
        g = StubComfy.graphs[0]
        self.assertEqual(g["10"]["inputs"]["image"], "aster-regen/happy.png")
        self.assertEqual(g["20"]["inputs"]["pixels"], ["10", 0])
        self.assertEqual(g["21"]["inputs"]["denoise"], 0.55)
        self.assertNotIn("11", g)  # no background composite for full sprites
        self.assertTrue(g["3"]["inputs"]["text"].startswith("asterfen,"))
        self.assertIn("splashing in the ocean", g["3"]["inputs"]["text"])
        self.assertTrue(g["30"]["inputs"]["filename_prefix"].startswith("aster/regen-"))

    def test_chibi_gets_flat_background_and_keeps_its_size(self):
        self.assertEqual(self.run_regen("--only", "wave_02_cut", "--seeds", "1",
                                        "--denoise", "0.6"), 0)
        g = StubComfy.graphs[0]
        self.assertEqual(g["11"]["inputs"]["color"], (191 << 16) | (232 << 8) | 208)
        self.assertEqual(g["12"]["inputs"]["mask"], ["10", 1])  # alpha, not 1 - alpha
        self.assertEqual((g["14"]["inputs"]["width"], g["14"]["inputs"]["height"]), (1024, 1280))
        self.assertEqual((g["23"]["inputs"]["width"], g["23"]["inputs"]["height"]), (512, 640))
        self.assertEqual(g["30"]["inputs"]["images"], ["23", 0])
        self.assertIn("flat mint green background", g["3"]["inputs"]["text"])
        self.assertIn("chibi", g["3"]["inputs"]["text"])

    def test_missing_lora_stops_before_queueing(self):
        StubComfy.loras = ["something-else.safetensors"]
        self.assertEqual(self.run_regen("--only", "happy"), 2)
        self.assertEqual(StubComfy.graphs, [])

    def test_missing_source_is_skipped_not_fatal(self):
        self.assertEqual(self.run_regen("--only", "idle", "happy", "--seeds", "1"), 0)
        self.assertEqual(StubComfy.uploads, ["happy.png"])

    def test_dry_run_touches_nothing(self):
        self.assertEqual(regen.main(["--dry-run", "--only", "dance", "--comfy", "http://127.0.0.1:9"]), 0)
        self.assertEqual(StubComfy.graphs, [])


if __name__ == "__main__":
    unittest.main()
