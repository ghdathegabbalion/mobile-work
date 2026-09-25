#!/usr/bin/env python3
"""Tests for the Aster app. Stdlib unittest only, like the app itself.

    python -m unittest discover -s tools/aster-app -p "test_*.py" -v   # repo root
    python -m unittest test_server -v                                   # in this folder
    python test_server.py                                               # also fine

No real network, no GPU, no ComfyUI: Aster's chat backend and ComfyUI are
stood in for by tiny http.server stubs on ephemeral 127.0.0.1 ports, and the
app itself is served in-process the same way. Runs under pytest too.
"""

import http.client
import io
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.parse
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import server  # noqa: E402


# ------------------------------------------------------------------ helpers


class Stub:
    """A throwaway HTTP server on an ephemeral port.

    routes: {(METHOD, path): fn(req) -> (code, headers, body)}. A path ending
    in * matches as a prefix. body is bytes/str, or an iterable of bytes that's
    written and flushed piece by piece - which is how the SSE stubs stream.
    Every request is recorded in .requests.
    """

    def __init__(self, routes):
        self.routes = routes
        self.requests = []
        stub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _go(self, method):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                parsed = urllib.parse.urlparse(self.path)
                req = {
                    "method": method,
                    "path": parsed.path,
                    "query": urllib.parse.parse_qs(parsed.query),
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": body,
                }
                stub.requests.append(req)
                fn = stub._route(method, parsed.path)
                if fn is None:
                    code, headers, out = 404, {"Content-Type": "text/plain"}, b"nope"
                else:
                    code, headers, out = fn(req)
                self.send_response(code)
                for key, val in headers.items():
                    self.send_header(key, val)
                if isinstance(out, (bytes, str)):
                    out = out.encode("utf-8") if isinstance(out, str) else out
                    self.send_header("Content-Length", str(len(out)))
                    self.end_headers()
                    self.wfile.write(out)
                    return
                self.end_headers()
                for piece in out:
                    self.wfile.write(piece)
                    self.wfile.flush()

            def do_GET(self):
                self._go("GET")

            def do_POST(self):
                self._go("POST")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, args=(0.05,), daemon=True).start()

    def _route(self, method, path):
        if (method, path) in self.routes:
            return self.routes[(method, path)]
        best = None
        for (m, p), fn in self.routes.items():
            if m == method and p.endswith("*") and path.startswith(p[:-1]):
                if best is None or len(p) > len(best[0]):
                    best = (p, fn)
        return best[1] if best else None

    def hits(self, path):
        return [r for r in self.requests if r["path"] == path]

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def js(obj, code=200):
    return code, {"Content-Type": "application/json"}, json.dumps(obj)


def sse_body(*events, gate=None, gate_after=None):
    """An SSE response. Each event is a data string (or raw bytes, sent as-is).
    With gate, pauses after `gate_after` events until the test releases it."""

    def gen():
        for i, ev in enumerate(events):
            if gate is not None and i == gate_after:
                gate.wait(5)
            yield ev if isinstance(ev, bytes) else f"data: {ev}\n\n".encode("utf-8")

    return 200, {"Content-Type": "text/event-stream"}, gen()


def comfy_routes(checkpoints=("sd_xl_base.safetensors", "ponyDiffusion.safetensors"),
                 new_format=False):
    """Just enough of ComfyUI's API for the app: stats, checkpoints, queue."""
    state = {"n": 0, "workflows": []}

    def info(_):
        opts = list(checkpoints)
        spec = ["COMBO", {"options": opts}] if new_format else [opts]
        return js({"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": spec}}}})

    def prompt(req):
        state["n"] += 1
        state["workflows"].append(json.loads(req["body"])["prompt"])
        return js({"prompt_id": f"p{state['n']}", "number": state["n"]})

    routes = {
        ("GET", "/system_stats"): lambda _: js({"devices": [{"name": "cuda:0 Test GPU"}]}),
        ("GET", "/object_info/CheckpointLoaderSimple"): info,
        ("POST", "/prompt"): prompt,
        ("GET", "/queue"): lambda _: js({"queue_running": [], "queue_pending": []}),
        ("GET", "/history/*"): lambda _: js({}),
        ("GET", "/view"): lambda _: (200, {"Content-Type": "image/png"}, b"FROMCOMFY"),
    }
    return routes, state


def config(**over):
    return server.deep_merge(server.DEFAULT_CONFIG, over)


def png_with_text(key, text):
    """A 1x1 PNG with a tEXt chunk, the way ComfyUI stashes its workflow."""
    png = server._png_bytes(1, [b"\x00\x00\x00"])
    data = key.encode("latin-1") + b"\x00" + text.encode("utf-8")
    chunk = (
        struct.pack(">I", len(data)) + b"tEXt" + data
        + struct.pack(">I", zlib.crc32(b"tEXt" + data) & 0xFFFFFFFF)
    )
    iend = png.rindex(b"\x00\x00\x00\x00IEND")
    return png[:iend] + chunk + png[iend:]


def closed_port():
    """A 127.0.0.1 port with nothing listening on it."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.stubs = []

    def tearDown(self):
        for stub in self.stubs:
            stub.close()
        self._tmp.cleanup()

    def stub(self, routes):
        s = Stub(routes)
        self.stubs.append(s)
        return s


# ------------------------------------------------------------------- config


class ConfigTests(TempDirCase):
    def test_missing_file_gives_defaults(self):
        cfg, err = server.load_config(self.tmp / "nope.json")
        self.assertIsNone(err)
        self.assertEqual(cfg, server.DEFAULT_CONFIG)

    def test_defaults_are_a_copy(self):
        # Regression: load_config used to return dict(DEFAULT_CONFIG), so
        # App's cfg["comfy"]["url"] = --comfy wrote through into the defaults.
        cfg, _ = server.load_config(self.tmp / "nope.json")
        cfg["comfy"]["url"] = "http://elsewhere:1"
        cfg["http"]["headers"]["X"] = "y"
        self.assertEqual(server.DEFAULT_CONFIG["comfy"]["url"], "http://127.0.0.1:8000")
        self.assertEqual(server.DEFAULT_CONFIG["http"]["headers"], {})

    def test_partial_override_deep_merges_without_sharing(self):
        path = self.tmp / "c.json"
        path.write_text(json.dumps({"backend": "cli", "http": {"url": "http://x/chat"}}))
        cfg, err = server.load_config(path)
        self.assertIsNone(err)
        self.assertEqual(cfg["backend"], "cli")
        self.assertEqual(cfg["http"]["url"], "http://x/chat")
        self.assertEqual(cfg["http"]["style"], "auto")  # kept from defaults
        self.assertFalse(cfg["http"]["stream"])
        cfg["comfy"]["steps"] = 99  # untouched section must not be shared either
        self.assertEqual(server.DEFAULT_CONFIG["comfy"]["steps"], 30)

    def test_invalid_json_reports_and_falls_back(self):
        path = self.tmp / "c.json"
        path.write_text("{nope")
        cfg, err = server.load_config(path)
        self.assertIn("not valid JSON", err)
        self.assertEqual(cfg, server.DEFAULT_CONFIG)

    def test_non_object_reports(self):
        path = self.tmp / "c.json"
        path.write_text("[1, 2]")
        cfg, err = server.load_config(path)
        self.assertIn("JSON object", err)
        self.assertEqual(cfg["backend"], "auto")

    def test_example_config_loads_and_matches_defaults(self):
        cfg, err = server.load_config(HERE / "aster.config.example.json")
        self.assertIsNone(err)
        for section in ("http", "cli", "comfy"):
            for key, val in server.DEFAULT_CONFIG[section].items():
                self.assertEqual(cfg[section][key], val, f"{section}.{key}")

    def test_deep_merge_replaces_non_dicts(self):
        out = server.deep_merge({"a": {"b": 1, "c": 2}, "d": [1]}, {"a": {"b": 9}, "d": None})
        self.assertEqual(out, {"a": {"b": 9, "c": 2}, "d": None})


class PromptFileTests(TempDirCase):
    def test_comments_are_stripped_and_lines_joined(self):
        path = self.tmp / "aster-prompt.txt"
        path.write_text(
            "asterfen, masterpiece,\n"
            "cream fur, (single tail:1.4),\n"
            "\n"
            "# NEVER include \"many arms for parallel work\" - it grows extra tentacles\n"
            "   # indented comment, extra tentacles\n"
            "crisp linework\n",
            encoding="utf-8",
        )
        text = server.read_prompt_file(path)
        self.assertEqual(
            text, "asterfen, masterpiece, cream fur, (single tail:1.4), crisp linework"
        )
        self.assertNotIn("many arms", text)
        self.assertNotIn("extra tentacles", text)
        self.assertNotIn("#", text)

    def test_missing_file_is_none(self):
        self.assertIsNone(server.read_prompt_file(self.tmp / "nope.txt"))

    def test_resolve_text_strips_config_path_and_fallback_file(self):
        path = self.tmp / "neg.txt"
        path.write_text("bad hands,\n# a note about many arms\nblurry\n")
        self.assertEqual(server.App._resolve_text(str(path), None), (path, "bad hands, blurry"))
        self.assertEqual(server.App._resolve_text(None, path), (path, "bad hands, blurry"))
        # a literal string in the config is taken as-is, comments and all
        self.assertEqual(server.App._resolve_text(" # literally ", None), (None, "# literally"))
        self.assertEqual(server.App._resolve_text(None, None), (None, None))

    def test_real_aster_prompt_file_reaches_clip_clean(self):
        real = HERE.parent.parent / "characters" / "aster-prompt.txt"
        if not real.is_file():
            self.skipTest("characters/aster-prompt.txt not in this checkout")
        text = server.read_prompt_file(real)
        self.assertTrue(text.startswith("asterfen"), "LoRA trigger word must stay first")
        self.assertNotIn("#", text)
        self.assertNotIn("many arms for parallel work", text)
        self.assertNotIn("\n", text)


# ---------------------------------------------------------------- discovery


ASTER_PAGE = """<!doctype html><html><head><title>  Aster
  Console </title>
<script src="/static/app.js"></script>
<script src="//127.0.0.1:{other}/lib.js"></script>
<script src="http://127.0.0.1:{other}/cdn.js"></script>
</head><body><script>
fetch('/api/health').then(r => r.json());
fetch(`${{base}}/api/secret`);
fetch("/img/logo.png");
</script></body></html>"""

ASTER_JS = """
async function send(t){ return fetch("/api/chat", {method: "POST", body: t}); }
const ws = new WebSocket("ws://127.0.0.1:8787/ws/live");
const es = new EventSource('/events');
axios.get('/api/messages');
"""


class DiscoveryTests(TempDirCase):
    def aster(self, page, js=""):
        other = self.stub({("GET", "/lib.js"): lambda _: (200, {}, "fetch('/api/chat-cdn')"),
                           ("GET", "/cdn.js"): lambda _: (200, {}, "fetch('/api/chat-cdn')")})
        routes = {
            ("GET", "/"): lambda _: (200, {"Content-Type": "text/html"},
                                     page.format(other=other.httpd.server_address[1])),
            ("GET", "/static/app.js"): lambda _: (200, {"Content-Type": "text/javascript"}, js),
        }
        return self.stub(routes), other

    def test_finds_calls_in_page_and_same_origin_bundle(self):
        aster, other = self.aster(ASTER_PAGE, ASTER_JS)
        found = server.discover_aster(aster.url, timeout=2)
        self.assertTrue(found["ok"])
        self.assertEqual(found["title"], "Aster Console")
        paths = [c["path"] for c in found["candidates"]]
        self.assertEqual(paths[0], "/api/chat")  # chatty + fetch ranks first
        self.assertIn("/api/health", paths)
        self.assertIn("/ws/live", paths)
        self.assertIn("/events", paths)
        self.assertNotIn("/img/logo.png", paths)  # assets aren't endpoints
        self.assertFalse(any("secret" in p for p in paths))  # template URLs skipped
        kinds = {c["path"]: c["kind"] for c in found["candidates"]}
        self.assertEqual(kinds["/ws/live"], "ws")
        self.assertEqual(kinds["/events"], "sse")

    def test_cross_origin_scripts_are_never_fetched(self):
        # Regression: a protocol-relative //host/x.js slipped past the old
        # startswith(base) check and got fetched.
        aster, other = self.aster(ASTER_PAGE, ASTER_JS)
        found = server.discover_aster(aster.url, timeout=2)
        self.assertEqual(other.requests, [])
        self.assertFalse(any("chat-cdn" in c["path"] for c in found["candidates"]))

    def test_best_endpoint_is_the_chatty_fetch(self):
        aster, _ = self.aster(ASTER_PAGE, ASTER_JS)
        best = server.best_chat_endpoint(server.discover_aster(aster.url, timeout=2))
        self.assertEqual(best["url"], aster.url + "/api/chat")

    def test_no_chatty_endpoint_is_ambiguous(self):
        aster, _ = self.aster("<script>fetch('/api/health')</script>")
        found = server.discover_aster(aster.url, timeout=2)
        self.assertIsNone(server.best_chat_endpoint(found))
        self.assertIn("no obviously chat-shaped", server.describe_discovery(found))

    def test_socket_only_page_says_so(self):
        aster, _ = self.aster("<script>new WebSocket('ws://127.0.0.1:1/chat')</script>")
        found = server.discover_aster(aster.url, timeout=2)
        self.assertIsNone(server.best_chat_endpoint(found))
        self.assertIn("WebSocket", server.describe_discovery(found))

    def test_nothing_answering(self):
        found = server.discover_aster(f"http://127.0.0.1:{closed_port()}", timeout=2)
        self.assertFalse(found["ok"])
        self.assertIn("nothing answering", server.describe_discovery(found))
        self.assertEqual(server.discover_aster("")["error"], "no asterUrl configured")

    def test_build_backend_wires_discovered_endpoint(self):
        aster, _ = self.aster(ASTER_PAGE, ASTER_JS)
        backend, notes = server.build_backend(config(asterUrl=aster.url), "sys")
        self.assertEqual(backend.name, "http")
        self.assertEqual(backend.url, aster.url + "/api/chat")
        self.assertIn("[discovered]", backend.detail)

    def test_build_backend_falls_back_to_echo(self):
        dead = f"http://127.0.0.1:{closed_port()}"
        backend, notes = server.build_backend(config(backend="http", asterUrl=dead), "sys")
        self.assertEqual(backend.name, "echo")
        self.assertTrue(notes and notes[0].startswith("http: nothing answering"))
        backend, _ = server.build_backend(config(backend="echo"), "sys")
        self.assertEqual(backend.name, "echo")


# ------------------------------------------------------------ chat backends


class HttpBackendTests(TempDirCase):
    def backend(self, url, **http):
        return server.HttpBackend(config(http=dict(http, url=url)), "SYSTEM")

    HISTORY = [
        {"role": "user", "text": "hi"},
        {"role": "assistant", "text": "hello"},
        {"role": "system", "text": "not sent"},
    ]

    def test_openai_shape(self):
        aster = self.stub({("POST", "/v1/chat/completions"): lambda _: js(
            {"choices": [{"message": {"role": "assistant", "content": "Moon!"}}]})})
        b = self.backend(aster.url + "/v1/chat/completions", headers={"Authorization": "k"})
        self.assertEqual(b.style, "openai")  # auto, by URL
        self.assertEqual(list(b.stream("draw?", self.HISTORY)), ["Moon!"])
        req = aster.requests[0]
        payload = json.loads(req["body"])
        self.assertEqual(payload["model"], "aster")
        self.assertIs(payload["stream"], False)  # unchanged unless http.stream
        self.assertEqual(
            payload["messages"],
            [
                {"role": "system", "content": "SYSTEM"},
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
                {"role": "user", "content": "draw?"},
            ],
        )
        self.assertEqual(req["headers"]["authorization"], "k")
        self.assertNotIn("text/event-stream", req["headers"].get("accept", ""))

    def test_simple_shape_and_reply_keys(self):
        replies = iter([
            js({"reply": "a"}), js({"text": "b"}), js({"content": "c"}),
            js({"response": "d"}), js({"message": {"role": "assistant", "content": "e"}}),
            (200, {"Content-Type": "text/plain"}, "  plain f  "), js("g"),
        ])
        aster = self.stub({("POST", "/api/chat"): lambda _: next(replies)})
        b = self.backend(aster.url + "/api/chat")
        self.assertEqual(b.style, "simple")
        got = ["".join(b.stream("m", self.HISTORY)) for _ in range(7)]
        self.assertEqual(got, ["a", "b", "c", "d", "e", "plain f", "g"])
        payload = json.loads(aster.requests[0]["body"])
        self.assertEqual(payload["message"], "m")
        self.assertEqual(payload["system"], "SYSTEM")
        self.assertEqual(payload["history"], [
            {"role": "user", "text": "hi"}, {"role": "assistant", "text": "hello"}])
        self.assertNotIn("stream", payload)

    def test_unknown_json_is_shown_not_lost(self):
        self.assertEqual(server.HttpBackend._extract('{"odd": 1}'), '{"odd": 1}')
        self.assertEqual(server.HttpBackend._extract('{"choices": [{"text": "t"}]}'), "t")

    def test_http_error_and_unreachable(self):
        aster = self.stub({("POST", "/api/chat"): lambda _: (500, {}, "boom")})
        with self.assertRaisesRegex(server.BackendError, "HTTP 500: boom"):
            list(self.backend(aster.url + "/api/chat").stream("m", []))
        with self.assertRaisesRegex(server.BackendError, "Could not reach"):
            list(self.backend(f"http://127.0.0.1:{closed_port()}/chat").stream("m", []))


class SseParsingTests(unittest.TestCase):
    def test_iter_sse(self):
        raw = (
            b": keep-alive\r\n"
            b"event: token\r\n"
            b"data: line one\r\n"
            b"data:  two, with its own space\r\n"
            b"id: 7\r\n"
            b"\r\n"
            b"data: {\"a\": 1}\n"
            b"\n"
            b"\n"
            b"data: unterminated"
        )
        self.assertEqual(
            list(server.iter_sse(io.BytesIO(raw))),
            [
                ("token", "line one\n two, with its own space"),
                ("message", '{"a": 1}'),
                ("message", "unterminated"),
            ],
        )

    def test_delta_shapes(self):
        d = server.sse_delta
        self.assertEqual(d(" world"), " world")  # raw text
        self.assertEqual(d('"quoted"'), "quoted")
        self.assertEqual(d('{"choices":[{"delta":{"content":"Hi"}}]}'), "Hi")
        self.assertEqual(d('{"choices":[{"delta":{"role":"assistant"}}]}'), "")
        self.assertEqual(d('{"choices":[{"delta":{},"finish_reason":"stop"}]}'), "")
        self.assertEqual(d('{"choices":[{"text":"legacy"}]}'), "legacy")
        self.assertEqual(d('{"choices":[]}'), "")  # usage-only chunk
        self.assertEqual(d('{"text":"t"}'), "t")
        self.assertEqual(d('{"content":"c"}'), "c")
        self.assertEqual(d('{"delta":"dl"}'), "dl")
        self.assertEqual(d('{"token":"tk"}'), "tk")
        self.assertEqual(d('{"token":{"id":5,"text":"tgi"}}'), "tgi")
        self.assertEqual(d('{"type":"content_block_delta","delta":{"type":"text_delta","text":"an"}}'), "an")
        self.assertEqual(d('{"type":"message_stop"}'), "")
        self.assertEqual(d('{"done":true}'), "")
        self.assertEqual(d("42"), "42")
        self.assertIsNone(d('{"weird":1}'))
        self.assertIsNone(d("[1, 2]"))

    def test_errors(self):
        e = server.sse_error
        self.assertEqual(e("error", "rate limited"), "rate limited")
        self.assertEqual(e("message", '{"error":{"message":"overloaded"}}'), "overloaded")
        self.assertEqual(e("message", '{"error":"nope"}'), "nope")
        self.assertIsNone(e("message", '{"error":null,"text":"ok"}'))
        self.assertIsNone(e("message", "plain"))


class HttpSseTests(TempDirCase):
    def backend(self, url, **http):
        return server.HttpBackend(config(http=dict(http, url=url)), "SYSTEM")

    def test_openai_stream_is_progressive(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        aster = self.stub({("POST", "/v1/chat/completions"): lambda _: sse_body(
            '{"choices":[{"delta":{"role":"assistant"}}]}',
            '{"choices":[{"delta":{"content":"Hel"}}]}',
            '{"choices":[{"delta":{"content":"lo"}}]}',
            '{"choices":[{"delta":{},"finish_reason":"stop"}]}',
            "[DONE]",
            b"data: {\"choices\":[{\"delta\":{\"content\":\"after DONE\"}}]}\n\n",
            gate=gate, gate_after=2,
        )})
        b = self.backend(aster.url + "/v1/chat/completions", stream=True)
        chunks = b.stream("hi", [])
        start = time.monotonic()
        self.assertEqual(next(chunks), "Hel")
        # the stub is still holding the rest back, so this arrived live
        self.assertLess(time.monotonic() - start, 3)
        self.assertFalse(gate.is_set())
        gate.set()
        self.assertEqual(list(chunks), ["lo"])  # stops at [DONE]
        req = aster.requests[0]
        self.assertIs(json.loads(req["body"])["stream"], True)
        self.assertIn("text/event-stream", req["headers"]["accept"])

    def test_simple_style_stream_request(self):
        aster = self.stub({("POST", "/chat"): lambda _: sse_body("a", "b")})
        b = self.backend(aster.url + "/chat", stream=True)
        self.assertEqual(list(b.stream("m", [])), ["a", "b"])
        self.assertIs(json.loads(aster.requests[0]["body"])["stream"], True)

    def test_event_stream_reply_is_streamed_even_unasked(self):
        aster = self.stub({("POST", "/chat"): lambda _: sse_body(
            '{"text":"one "}', '{"token":"two "}', '{"delta":{"text":"three"}}')})
        self.assertEqual(list(self.backend(aster.url + "/chat").stream("m", [])),
                         ["one ", "two ", "three"])

    def test_mistyped_event_stream_still_reads(self):
        body = 'data: {"content":"x"}\n\ndata: {"content":"y"}\n\ndata: [DONE]\n\n'
        aster = self.stub({("POST", "/chat"): lambda _: (200, {"Content-Type": "text/plain"}, body)})
        self.assertEqual(list(self.backend(aster.url + "/chat").stream("m", [])), ["x", "y"])

    def test_error_event_raises(self):
        aster = self.stub({("POST", "/chat"): lambda _: sse_body(
            '{"text":"par"}', b"event: error\ndata: model crashed\n\n")})
        chunks = self.backend(aster.url + "/chat").stream("m", [])
        self.assertEqual(next(chunks), "par")
        with self.assertRaisesRegex(server.BackendError, "model crashed"):
            next(chunks)

    def test_unknown_shape_is_reported(self):
        aster = self.stub({("POST", "/chat"): lambda _: sse_body('{"weird":1}', '{"odd":2}')})
        with self.assertRaisesRegex(server.BackendError, 'first was: {"weird":1}'):
            list(self.backend(aster.url + "/chat").stream("m", []))

    def test_stalled_stream_keeps_what_arrived(self):
        # Aster sends half a reply, then goes quiet past the read timeout.
        gate = threading.Event()
        self.addCleanup(gate.set)
        aster = self.stub({("POST", "/chat"): lambda _: sse_body(
            '{"text":"half a rep"}', '{"text":"ly"}', gate=gate, gate_after=1)})
        got = list(self.backend(aster.url + "/chat", timeoutSeconds=1).stream("m", []))
        self.assertEqual(got[0], "half a rep")
        self.assertEqual(len(got), 2)
        self.assertIn("[cut off", got[1])


class CliBackendTests(TempDirCase):
    def backend(self, script, **cli):
        cmd = [sys.executable, "-c", script]
        return server.CliBackend(config(cli=dict(cli, command=cmd, cwd=str(self.tmp))), "SYSTEM")

    def test_prompt_in_reply_out(self):
        b = self.backend("import sys; print(sys.stdin.read().upper())")
        history = [{"role": "user", "text": "earlier"}, {"role": "assistant", "text": "yes"}]
        out = "".join(b.stream("now", history))
        self.assertIn("SYSTEM", out)
        self.assertIn("USER: EARLIER", out)
        self.assertIn("ASTER: YES", out)
        self.assertIn("USER: NOW", out)
        self.assertIn("REPLY AS ASTER.", out)

    def test_history_can_be_left_out(self):
        b = self.backend("import sys; print(sys.stdin.read())", includeHistory=False)
        out = "".join(b.stream("now", [{"role": "user", "text": "earlier"}]))
        self.assertNotIn("earlier", out)

    def test_noisy_stderr_does_not_deadlock(self):
        # Regression: stderr wasn't drained while stdout was read, so a CLI
        # logging more than a pipe buffer to stderr hung until the timeout.
        b = self.backend(
            "import sys; sys.stderr.write('x' * 300000); sys.stderr.flush(); print('ok')",
            timeoutSeconds=20,
        )
        start = time.monotonic()
        self.assertEqual("".join(b.stream("m", [])).strip(), "ok")
        self.assertLess(time.monotonic() - start, 10)

    def test_phone_leaving_kills_the_process(self):
        b = self.backend(
            "import sys, time; print('first', flush=True); time.sleep(30); print('late')",
            timeoutSeconds=60,
        )
        chunks = b.stream("m", [])
        self.assertEqual(next(chunks).strip(), "first")
        start = time.monotonic()
        chunks.close()  # what the handler's generator sees when the phone hangs up
        self.assertLess(time.monotonic() - start, 3)

    def test_no_output_reports_stderr(self):
        b = self.backend("import sys; sys.stderr.write('bad key'); sys.exit(3)")
        with self.assertRaisesRegex(server.BackendError, "exit 3.*\\n.*bad key"):
            list(b.stream("m", []))

    def test_missing_command(self):
        with self.assertRaisesRegex(server.BackendError, "command not found"):
            server.CliBackend(config(cli={"command": ["definitely-not-a-cmd-xyz"]}), "s")


class EchoBackendTests(unittest.TestCase):
    def test_stub_offers_render_only_when_asked(self):
        b = server.EchoBackend(config(), "s")
        self.assertNotIn("```render", "".join(b.stream("hello", [])))
        out = "".join(b.stream('draw a "fox"', []))
        _, specs = server.extract_directives(out)
        self.assertEqual(specs[0]["prompt"], "draw a 'fox'")


# ------------------------------------------------------------------ renders


class DirectiveTests(unittest.TestCase):
    def test_fenced_json_inline_and_bare(self):
        text = (
            "Here you go.\n\n```render\n"
            '{"prompt": "aster, moonlit garden", "aspect": "landscape", "seed": 5}\n```\n\n\n'
            "And [[render: a close-up]]"
        )
        clean, specs = server.extract_directives(text)
        self.assertEqual(clean, "Here you go.\n\nAnd")
        self.assertEqual(specs, [
            {"prompt": "aster, moonlit garden", "aspect": "landscape", "seed": 5},
            {"prompt": "a close-up"},
        ])
        _, specs = server.extract_directives("```render\n  a cat\n  wizard\n```")
        self.assertEqual(specs, [{"prompt": "a cat wizard"}])

    def test_near_miss_json_is_salvaged(self):
        _, specs = server.extract_directives('```render\n{"prompt": "fox", "steps": 20,}\n```')
        self.assertEqual(specs, [{"prompt": "fox"}])

    def test_capped_at_two(self):
        _, specs = server.extract_directives("[[render: a]] [[render: b]] [[render: c]]")
        self.assertEqual([s["prompt"] for s in specs], ["a", "b"])

    def test_non_string_prompt_is_dropped_not_fatal(self):
        # Regression: {"prompt": [...]} raised AttributeError mid-reply.
        clean, specs = server.extract_directives('ok ```render\n{"prompt": ["a", "b"]}\n```')
        self.assertEqual((clean, specs), ("ok", []))


class FakeComfy:
    def __init__(self, model="m.safetensors"):
        self.model = model
        self.submitted = []
        self.queue = (set(), set())
        self.entries = {}

    def pick_model(self):
        return self.model

    def submit(self, workflow):
        self.submitted.append(workflow)
        return f"p{len(self.submitted)}"

    def queued_ids(self):
        return self.queue

    def history(self, pid):
        return self.entries.get(pid)


class RenderTests(TempDirCase):
    def service(self, **over):
        comfy = FakeComfy()
        return server.RenderService(config(**over), comfy), comfy

    def test_default_graph(self):
        svc, comfy = self.service(renderPrefix="asterfen, 1girl")
        job = svc.queue({"prompt": "moon garden", "aspect": "landscape", "seed": "42",
                         "steps": "", "cfg": ""})
        wf = comfy.submitted[0]
        self.assertEqual(wf["4"]["inputs"]["ckpt_name"], "m.safetensors")
        self.assertEqual(wf["6"]["inputs"]["text"], "asterfen, 1girl, moon garden")
        self.assertEqual(wf["7"]["inputs"]["text"], server.DEFAULT_NEGATIVE)
        self.assertEqual((wf["5"]["inputs"]["width"], wf["5"]["inputs"]["height"]), (1216, 832))
        ks = wf["3"]["inputs"]
        self.assertEqual((ks["seed"], ks["steps"], ks["cfg"]), (42, 30, 6.5))
        self.assertEqual((ks["sampler_name"], ks["scheduler"]), ("dpmpp_2m", "karras"))
        self.assertEqual(wf["9"]["inputs"]["filename_prefix"], "aster/Aster")
        self.assertEqual(job["size"], "1216x832")
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["promptId"], "p1")

    def test_prefix_not_doubled_and_seed_random(self):
        svc, comfy = self.service(renderPrefix="asterfen")
        job = svc.queue({"prompt": "AsterFen at the beach", "seed": 0})
        self.assertEqual(job["prompt"], "AsterFen at the beach")
        self.assertTrue(1 <= job["seed"] < 2 ** 31)
        self.assertEqual(svc.queue({"prompt": "x", "negative": "n"})["prompt"], "asterfen, x")
        self.assertEqual(comfy.submitted[-1]["7"]["inputs"]["text"], "n")

    def test_empty_prompt_refused(self):
        svc, _ = self.service()
        with self.assertRaisesRegex(server.BackendError, "No prompt"):
            svc.queue({"prompt": "  "})

    def test_workflow_override_placeholders(self):
        path = self.tmp / "wf.json"
        path.write_text(json.dumps({
            "1": {"inputs": {"text": "%positive%", "neg": "%negative%", "steps": "%steps%",
                             "cfg": "%cfg%", "seed": " %seed% ", "size": "%width%x%height%",
                             "ckpt": "%model%", "prefix": "%prefix%", "keep": "%unknown%"}},
            "2": [{"nested": "%steps% steps"}],
        }))
        svc, comfy = self.service(comfy={"workflow": str(path), "steps": 12})
        svc.queue({"prompt": "p", "aspect": "square", "seed": 7, "cfg": "4"})
        ins = comfy.submitted[0]["1"]["inputs"]
        self.assertEqual(ins["steps"], 12)  # whole-value placeholders keep their type
        self.assertEqual(ins["cfg"], 4.0)
        self.assertEqual(ins["seed"], 7)
        self.assertEqual(ins["size"], "1024x1024")
        self.assertEqual(ins["text"], "p")
        self.assertEqual(ins["ckpt"], "m.safetensors")
        self.assertEqual(ins["prefix"], "aster/Aster")
        self.assertEqual(ins["keep"], "%unknown%")
        self.assertEqual(comfy.submitted[0]["2"], [{"nested": "12 steps"}])

    def test_missing_workflow_file(self):
        svc, _ = self.service(comfy={"workflow": str(self.tmp / "nope.json")})
        with self.assertRaisesRegex(server.BackendError, "workflow file"):
            svc.queue({"prompt": "p"})

    def test_refresh_states(self):
        svc, comfy = self.service()
        a, b, c = (svc.queue({"prompt": x}) for x in "abc")
        comfy.queue = ({a["promptId"]}, {b["promptId"]})
        svc.refresh()
        self.assertEqual((a["status"], b["status"], c["status"]), ("running", "queued", "queued"))

        comfy.entries[a["promptId"]] = {"status": {"status_str": "success"}, "outputs": {
            "9": {"images": [{"filename": "A_1.png", "subfolder": "aster", "type": "output"},
                             {"filename": "tmp.png", "type": "temp"}]}}}
        comfy.entries[b["promptId"]] = {"status": {"status_str": "error", "messages": [
            ["execution_error", {"node_type": "KSampler", "exception_message": "OOM"}]]}}
        c["created"] -= 60
        comfy.queue = (set(), set())
        svc.refresh()
        self.assertEqual((a["status"], a["images"]), ("done", ["aster/A_1.png"]))
        self.assertEqual((b["status"], b["error"]), ("error", "KSampler - OOM"))
        self.assertEqual((c["status"], c["error"]), ("error", "disappeared from the ComfyUI queue"))

    def test_unreachable_comfy_does_not_fail_jobs(self):
        # Regression: an unreachable /queue read as "empty", so after 30s every
        # in-flight job was marked "disappeared" during a ComfyUI hiccup.
        svc, comfy = self.service()
        job = svc.queue({"prompt": "a"})
        job["created"] -= 600
        comfy.queue = None
        svc.refresh()
        self.assertEqual(job["status"], "queued")


class ComfyClientTests(TempDirCase):
    def comfy(self, **kw):
        routes, state = comfy_routes(**kw)
        stub = self.stub(routes)
        return server.Comfy(config(comfy={"url": stub.url + "/"})), stub, state

    def test_status_and_model_pick(self):
        comfy, _, _ = self.comfy()
        self.assertEqual(comfy.status(), (True, "cuda:0 Test GPU"))
        self.assertEqual(comfy.pick_model(), "ponyDiffusion.safetensors")

    def test_new_combo_format(self):
        # Regression: ["COMBO", {"options": [...]}] became checkpoints C, O, M, B, O.
        comfy, _, _ = self.comfy(new_format=True)
        self.assertEqual(comfy.checkpoints(),
                         ["sd_xl_base.safetensors", "ponyDiffusion.safetensors"])

    def test_configured_model_wins_and_empty_list_explains(self):
        comfy, _, _ = self.comfy(checkpoints=())
        with self.assertRaisesRegex(server.BackendError, "no checkpoints"):
            comfy.pick_model()
        comfy.cfg["model"] = "mine.safetensors"
        self.assertEqual(comfy.pick_model(), "mine.safetensors")

    def test_down(self):
        comfy = server.Comfy(config(comfy={"url": f"http://127.0.0.1:{closed_port()}"}))
        up, detail = comfy.status()
        self.assertFalse(up)
        self.assertIn("not reachable", detail)
        with self.assertRaisesRegex(server.BackendError, "ComfyUI is not reachable"):
            comfy.pick_model()
        self.assertIsNone(comfy.queued_ids())

    def test_submit(self):
        comfy, stub, state = self.comfy()
        self.assertEqual(comfy.submit({"1": {}}), "p1")
        self.assertEqual(json.loads(stub.hits("/prompt")[0]["body"])["client_id"], "aster-app")
        stub.routes[("POST", "/prompt")] = lambda _: (400, {}, '{"error": "bad node"}')
        with self.assertRaisesRegex(server.BackendError, "rejected the workflow.*bad node"):
            comfy.submit({})


# ------------------------------------------------------------------ gallery


class GalleryTests(TempDirCase):
    def setUp(self):
        super().setUp()
        self.root = self.tmp / "output"
        (self.root / "aster").mkdir(parents=True)
        (self.root / "old.png").write_bytes(b"old")
        (self.root / "aster" / "new.webp").write_bytes(b"new")
        (self.root / "notes.txt").write_text("not an image")
        os.utime(self.root / "old.png", (1000, 1000))
        (self.tmp / "secret.png").write_bytes(b"outside")

    def test_list_images(self):
        names = [i["name"] for i in server.list_images(self.root)]
        self.assertEqual(names, ["aster/new.webp", "old.png"])  # newest first, posix
        self.assertEqual(server.list_images(self.tmp / "nope"), [])
        self.assertEqual(server.list_images(None), [])

    def test_safe_join_inside(self):
        self.assertEqual(server.safe_join(self.root, "aster/new.webp"),
                         self.root / "aster" / "new.webp")
        self.assertEqual(server.safe_join(self.root, "/aster%2Fnew.webp"),
                         self.root / "aster" / "new.webp")

    def test_safe_join_refuses_escapes(self):
        for rel in ("../secret.png", "%2e%2e/secret.png", "aster/../../secret.png",
                    "..%2Fsecret.png", "..\\secret.png", str(self.tmp / "secret.png"),
                    "", "aster", "missing.png"):
            with self.subTest(rel=rel):
                self.assertIsNone(server.safe_join(self.root, rel))
        self.assertIsNone(server.safe_join(None, "old.png"))

    def test_safe_join_nul_byte(self):
        # Regression: resolve() raised ValueError on %00 and killed the request.
        self.assertIsNone(server.safe_join(self.root, "old.png%00.jpg"))

    def test_safe_join_symlink_out(self):
        link = self.root / "sneaky.png"
        try:
            link.symlink_to(self.tmp / "secret.png")
        except (OSError, NotImplementedError):
            self.skipTest("no symlinks here")
        self.assertIsNone(server.safe_join(self.root, "sneaky.png"))

    def test_png_meta(self):
        wf = server.default_workflow("m.safetensors", "a fox", "blurry", 9, 20, 5.0,
                                     832, 1216, "aster/Aster", "euler", "normal")
        path = self.root / "meta.png"
        path.write_bytes(png_with_text("prompt", json.dumps(wf)))
        self.assertEqual(server.image_meta(path), {
            "seed": 9, "steps": 20, "cfg": 5.0, "sampler_name": "euler",
            "scheduler": "normal", "positive": "a fox", "negative": "blurry",
            "model": "m.safetensors", "width": 832, "height": 1216,
        })
        self.assertIsNone(server.image_meta(self.root / "aster" / "new.webp"))
        self.assertIsNone(server.summarize_workflow("not json"))


# --------------------------------------------------------------- HTTP routes


TOKEN = "s3cret-token"


class AppHarness(TempDirCase):
    """The real Handler, served in-process against a fake App and stub ComfyUI."""

    backend_factory = None

    def setUp(self):
        super().setUp()
        routes, self.comfy_state = comfy_routes()
        self.comfy_stub = self.stub(routes)
        cfg = config(comfy={"url": self.comfy_stub.url})
        comfy = server.Comfy(cfg)
        self.out = self.tmp / "output"
        (self.out / "aster").mkdir(parents=True)
        (self.out / "aster" / "a.png").write_bytes(png_with_text("prompt", json.dumps(
            server.default_workflow("m", "fox", "n", 1, 2, 3.0, 4, 5, "p", "s", "k"))))
        (self.tmp / "secret.png").write_bytes(b"outside")
        self.app = types.SimpleNamespace(
            config=cfg,
            comfy=comfy,
            renders=server.RenderService(cfg, comfy),
            transcript=server.Transcript(self.tmp / "chat.json"),
            output_dir=self.out,
            negative_source="built-in",
            backend=server.EchoBackend(cfg, "s"),
            backend_notes=[],
            token=TOKEN,
        )
        handler = type("TestHandler", (server.Handler,), {"app": self.app})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, args=(0.05,), daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        super().tearDown()

    def call(self, method, path, body=None, auth=True, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = dict(headers or {})
        if auth:
            h.setdefault("Cookie", f"aster={TOKEN}")
        data = body
        if body is not None and not isinstance(body, bytes):
            data = json.dumps(body).encode("utf-8")
            h["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=h)
        resp = conn.getresponse()
        out = resp.read()
        conn.close()
        return resp.status, resp.headers, out

    @staticmethod
    def frames(raw):
        parts = (p.strip() for p in raw.decode("utf-8").split("\n\n"))
        return [json.loads(p[5:]) for p in parts if p.startswith("data:")]


class RouteTests(AppHarness):
    def test_icons_and_manifests_need_no_token(self):
        status, headers, body = self.call("GET", "/icon.png", auth=False)
        self.assertEqual((status, headers["Content-Type"]), (200, "image/png"))
        self.assertTrue(body.startswith(b"\x89PNG"))
        status, _, body = self.call("GET", "/gallery.webmanifest", auth=False)
        self.assertEqual(json.loads(body)["start_url"], "/gallery")

    def test_token_flow(self):
        self.assertEqual(self.call("GET", "/", auth=False)[0], 401)
        status, headers, _ = self.call("GET", f"/gallery?t={TOKEN}", auth=False)
        self.assertEqual((status, headers["Location"]), (302, "/gallery"))
        self.assertIn(f"aster={TOKEN}", headers["Set-Cookie"])
        status, _, body = self.call("GET", "/gallery")
        self.assertEqual(status, 200)
        self.assertIn(b"const INIT_TAB='gallery'", body)
        self.assertIn(b"<title>Renders</title>", body)
        status, _, body = self.call("GET", "/api/hello", auth=False,
                                    headers={"X-Aster-Token": TOKEN})
        self.assertEqual(status, 200)
        self.assertEqual(self.call("POST", "/api/reset", auth=False)[0], 401)

    def test_non_ascii_token_is_refused_not_crashed(self):
        # Regression: compare_digest raised TypeError on a non-ASCII str.
        self.assertEqual(self.call("GET", "/?t=%C3%A9", auth=False)[0], 401)
        # headers go out latin-1, so these arrive as a non-ASCII str too
        self.assertEqual(self.call("GET", "/api/hello", auth=False,
                                   headers={"Cookie": "aster=é"})[0], 401)
        self.assertEqual(self.call("GET", "/api/hello", auth=False,
                                   headers={"X-Aster-Token": "été"})[0], 401)

    def test_hello(self):
        status, _, body = self.call("GET", "/api/hello")
        hello = json.loads(body)
        self.assertEqual(hello["backend"], "echo")
        self.assertTrue(hello["comfy"]["up"])
        self.assertEqual(hello["comfy"]["detail"], "cuda:0 Test GPU")

    def test_list_image_meta_thumb(self):
        status, _, body = self.call("GET", "/api/list")
        self.assertEqual([i["name"] for i in json.loads(body)], ["aster/a.png"])
        status, headers, body = self.call("GET", "/img/aster/a.png")
        self.assertEqual((status, headers["Content-Type"]), (200, "image/png"))
        self.assertEqual(self.call("GET", "/thumb/aster/a.png")[0], 200)
        status, _, body = self.call("GET", "/api/meta/aster/a.png")
        self.assertEqual(json.loads(body)["positive"], "fox")
        self.assertEqual(self.call("GET", "/api/meta/../secret.png")[0], 404)

    def test_traversal_never_leaves_output_or_reaches_comfy(self):
        for path in ("/img/../secret.png", "/img/%2e%2e/secret.png",
                     "/img/aster/%2e%2e/%2e%2e/secret.png", "/thumb/..%2fsecret.png",
                     "/img/..%5csecret.png", "/img/a%00.png"):
            with self.subTest(path=path):
                status, _, body = self.call("GET", path)
                self.assertNotEqual(body, b"outside")
        views = self.comfy_stub.hits("/view")
        for req in views:
            name = req["query"].get("filename", [""])[0]
            sub = req["query"].get("subfolder", [""])[0]
            self.assertNotIn("..", name + "/" + sub)

    def test_miss_falls_back_to_comfy_view(self):
        status, _, body = self.call("GET", "/img/aster/elsewhere.png")
        self.assertEqual((status, body), (200, b"FROMCOMFY"))
        q = self.comfy_stub.hits("/view")[-1]["query"]
        self.assertEqual((q["filename"], q["subfolder"], q["type"]),
                         (["elsewhere.png"], ["aster"], ["output"]))

    def test_render_and_jobs(self):
        status, _, body = self.call("POST", "/api/render", {"prompt": "fox", "aspect": "square"})
        self.assertEqual(status, 200)
        job = json.loads(body)
        self.assertEqual((job["size"], job["model"]), ("1024x1024", "ponyDiffusion.safetensors"))
        status, _, body = self.call("GET", "/api/jobs")
        self.assertEqual([j["id"] for j in json.loads(body)], [job["id"]])
        status, _, body = self.call("POST", "/api/render", {"prompt": ""})
        self.assertEqual((status, json.loads(body)["error"]), (502, "No prompt to render"))
        status, _, body = self.call("POST", "/api/render", {"prompt": "x", "steps": "lots"})
        self.assertEqual(status, 500)
        self.assertIn("ValueError", json.loads(body)["error"])

    def test_not_found(self):
        self.assertEqual(self.call("GET", "/nope")[0], 404)
        self.assertEqual(self.call("POST", "/api/nope", {})[0], 404)

    def test_reset(self):
        self.app.transcript.add("user", "x")
        self.call("POST", "/api/reset", {})
        self.assertEqual(self.app.transcript.history(), [])


class ChatRouteTests(AppHarness):
    def test_echo_chat_streams_and_queues_render(self):
        status, headers, raw = self.call("POST", "/api/chat", {"text": "draw a moonlit fox"})
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("text/event-stream"))
        frames = self.frames(raw)
        self.assertTrue(any("delta" in f for f in frames))
        done = frames[-1]
        self.assertTrue(done["done"])
        self.assertNotIn("```render", done["message"]["text"])
        self.assertEqual(len(done["message"]["newJobs"]), 1)
        self.assertEqual(len(self.comfy_state["workflows"]), 1)
        roles = [m["role"] for m in self.app.transcript.history()]
        self.assertEqual(roles, ["user", "assistant"])
        saved = json.loads((self.tmp / "chat.json").read_text())
        self.assertEqual(saved[1]["jobs"], [done["message"]["newJobs"][0]["id"]])

    def test_empty_and_malformed_bodies(self):
        self.assertEqual(self.call("POST", "/api/chat", {"text": "  "})[0], 400)
        # Regression: a JSON list body crashed the handler with no response.
        self.assertEqual(self.call("POST", "/api/chat", ["text"])[0], 400)
        self.assertEqual(self.call("POST", "/api/chat", b"not json",
                                   headers={"Content-Type": "application/json"})[0], 400)

    def test_bad_render_spec_keeps_the_reply(self):
        # Regression: {"steps": "lots"} raised ValueError after the stream was
        # open, so the phone got no done frame and the reply was never saved.
        class Bad:
            name, detail = "bad", ""

            def stream(self, message, history):
                yield 'Sure.\n```render\n{"prompt": "fox", "steps": "lots"}\n```'

        self.app.backend = Bad()
        _, _, raw = self.call("POST", "/api/chat", {"text": "draw"})
        done = self.frames(raw)[-1]
        self.assertTrue(done["done"])
        self.assertIn("Sure.", done["message"]["text"])
        self.assertIn("[render failed] ValueError", done["message"]["text"])

    def test_backend_error_becomes_error_frame(self):
        class Down:
            name, detail = "down", ""

            def stream(self, message, history):
                raise server.BackendError("Aster is asleep")
                yield  # pragma: no cover

        self.app.backend = Down()
        _, _, raw = self.call("POST", "/api/chat", {"text": "hi"})
        self.assertEqual(self.frames(raw), [{"error": "Aster is asleep"}])
        self.assertEqual(self.app.transcript.history()[-1]["text"], "[error] Aster is asleep")

    def test_sse_backend_streams_through_to_phone(self):
        """End to end: stub Aster streams SSE -> app -> phone, delta by delta."""
        gate = threading.Event()
        self.addCleanup(gate.set)
        aster = self.stub({("POST", "/v1/chat/completions"): lambda _: sse_body(
            '{"choices":[{"delta":{"role":"assistant"}}]}',
            '{"choices":[{"delta":{"content":"Drawing "}}]}',
            '{"choices":[{"delta":{"content":"it now.\\n```render\\n{\\"prompt\\": \\"fox\\"}\\n```"}}]}',
            "[DONE]",
            gate=gate, gate_after=2,
        )})
        self.app.backend = server.HttpBackend(
            config(http={"url": aster.url + "/v1/chat/completions", "stream": True}), "s")

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/chat", body=json.dumps({"text": "draw"}),
                     headers={"Cookie": f"aster={TOKEN}", "Content-Type": "application/json"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        first = None
        while first is None:
            line = resp.readline()
            self.assertTrue(line, "stream ended before the first delta")
            if line.startswith(b"data:"):
                first = json.loads(line[5:])
        # The phone has the first words while Aster is still holding the rest.
        self.assertEqual(first, {"delta": "Drawing "})
        self.assertFalse(gate.is_set())
        gate.set()
        frames = [first] + self.frames(resp.read())
        conn.close()
        done = frames[-1]
        self.assertTrue(done["done"])
        self.assertEqual(done["message"]["text"], "Drawing it now.")
        self.assertEqual(len(done["message"]["newJobs"]), 1)
        self.assertEqual("".join(f.get("delta", "") for f in frames[:-1]).split("\n")[0],
                         "Drawing it now.")


# -------------------------------------------------------------------- probe


class ProbeTests(unittest.TestCase):
    def test_probe_runs_offline(self):
        dead = f"http://127.0.0.1:{closed_port()}"
        proc = subprocess.run(
            [sys.executable, str(HERE / "server.py"), "--probe", "--no-token",
             "--backend", "echo", "--comfy", dead, "--aster", dead],
            capture_output=True, text=True, timeout=60, cwd=str(HERE),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("chat backend: echo", proc.stdout)
        self.assertIn("answered   : no", proc.stdout)
        self.assertIn("token       : DISABLED", proc.stdout)


if __name__ == "__main__":
    unittest.main()
