#!/usr/bin/env python3
"""Aster — phone front end for the Aster assistant on the home PC.

Chat with Aster and queue renders on the PC's GPU from a phone over Tailscale.
Stdlib only - no pip install. Pillow is used for thumbnails if it's importable.

    python server.py                 # start on :8778, print the phone URL
    python server.py --probe         # report what it can find, change nothing

Then open the printed 100.x URL on the phone and Add to Home Screen.

Aster's chat backend is pluggable (a local HTTP endpoint, or a CLI spawned per
turn) - see aster.config.example.json and the README. Renders go to the local
ComfyUI, default http://127.0.0.1:8000. When ComfyUI is reachable, Aster is told
it may ask for a render by emitting a ```render block; this server executes those
against ComfyUI itself, so the chat backend never needs tool permissions.
"""

import argparse
import glob
import hmac
import io
import json
import os
import posixpath
import random
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
THUMB_DIR = Path(tempfile.gettempdir()) / "aster-app-thumbs"
CONFIG_PATH = HERE / "aster.config.json"
TOKEN_PATH = HERE / "aster.token"
CHAT_PATH = HERE / "aster-chat.json"

OUTPUT_CANDIDATES = [
    "~/Documents/ComfyUI/output",  # ComfyUI Desktop's default
    r"C:\Users\GH-DA\ComfyUI-Shared\output",
    r"C:\Users\GH-DA\ComfyUI-Installs\ComfyUI\ComfyUI\output",
    r"C:\Users\GH-DA\ComfyUI\output",
    "~/ComfyUI/output",
    "./output",
]

# Where the Aster design material might live. A .txt is treated as a render
# prompt (prepended to what you type); a .md is treated as a design sheet and
# goes into Aster's chat context instead - pasting a whole markdown sheet into
# a sampler prompt makes for a terrible render.
CHARACTER_GLOBS = [
    r"C:\Users\GH-DA\ComfyUI-Shared\training\*aster*",
    r"C:\Users\GH-DA\mobile-work\characters\*aster*",
    str(HERE.parent.parent / "characters" / "*aster*"),
]

DEFAULT_NEGATIVE = (
    "worst quality, low quality, jpeg artifacts, blurry, lowres, "
    "bad anatomy, bad hands, extra fingers, extra limbs, deformed, mutated, "
    "cropped, out of frame, text, watermark, signature, logo, "
    "multiple views, character sheet, duplicate character"
)

DEFAULT_SYSTEM = (
    "You are Aster, a creative assistant running on GH-DA's home PC. "
    "You are being read on a phone screen: lead with the answer and keep replies "
    "short. Skip preambles."
)

# Appended to the system prompt only when ComfyUI is actually reachable, so
# Aster never offers to draw on a machine that can't.
RENDER_PROTOCOL = """
You can render images on this PC's GPU. To do it, end your reply with a fenced
block - the app strips the block out and queues the render, then shows the image
in the chat:

```render
{"prompt": "what to draw, as a comma-separated image prompt", "aspect": "portrait"}
```

"aspect" is portrait, square, or landscape. You may also add "negative", "steps",
"cfg", or "seed". A bare prompt works too: ```render\\na cat wizard, moonlight\\n```
Only emit the block when the user actually wants a picture, and at most two per
reply. Say in prose what you're rendering; don't describe the block itself.
"""

try:
    from PIL import Image  # noqa: F401

    HAVE_PIL = True
except Exception:
    HAVE_PIL = False


# ------------------------------------------------------------------- config


DEFAULT_CONFIG = {
    "backend": "auto",  # auto | http | cli | echo
    "systemPrompt": None,  # None -> DEFAULT_SYSTEM (+ design sheet, if found)
    # Aster's own web UI. Its page gets scraped for the endpoint it posts to,
    # so http.url can usually stay null.
    "asterUrl": "http://127.0.0.1:8787",
    "http": {
        "url": None,  # set to skip discovery, e.g. http://127.0.0.1:8787/chat
        "style": "auto",  # auto | openai | simple
        "model": "aster",
        "headers": {},
        "timeoutSeconds": 300,
    },
    "cli": {
        "command": None,  # None -> auto-detect the Claude Code CLI
        "cwd": None,
        "includeHistory": True,
        "historyTurns": 12,
        "timeoutSeconds": 300,
    },
    "comfy": {
        "url": "http://127.0.0.1:8000",
        "model": None,  # None -> first checkpoint ComfyUI reports
        "outputPrefix": "aster/Aster",
        "workflow": None,  # path to an API-format workflow with %positive% etc.
        "sampler": "dpmpp_2m",
        "scheduler": "karras",
        "steps": 30,
        "cfg": 6.5,
    },
    "renderPrefix": None,  # None -> a *.txt Aster prompt file, if one is found
    "renderNegative": None,
    "designSheet": None,  # None -> a *.md Aster sheet, if one is found
}


def deep_merge(base, over):
    out = dict(base)
    for key, val in (over or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_config(path=CONFIG_PATH):
    """Config file is optional - the defaults auto-detect a working setup."""
    if not path.is_file():
        return dict(DEFAULT_CONFIG), None
    try:
        user = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return dict(DEFAULT_CONFIG), f"{path.name} is not valid JSON: {exc}"
    if not isinstance(user, dict):
        return dict(DEFAULT_CONFIG), f"{path.name} must contain a JSON object"
    return deep_merge(DEFAULT_CONFIG, user), None


def find_character_files():
    """Split whatever Aster material exists into (prompt .txt, sheet .md)."""
    prompt_file = sheet_file = None
    for pattern in CHARACTER_GLOBS:
        for hit in sorted(glob.glob(os.path.expanduser(pattern))):
            path = Path(hit)
            if not path.is_file():
                continue
            low = path.name.lower()
            if "negative" in low:
                continue
            if path.suffix.lower() == ".txt" and prompt_file is None:
                prompt_file = path
            elif path.suffix.lower() == ".md" and sheet_file is None:
                sheet_file = path
    return prompt_file, sheet_file


def find_negative_file():
    for pattern in CHARACTER_GLOBS:
        for hit in sorted(glob.glob(os.path.expanduser(pattern))):
            if "negative" in Path(hit).name.lower() and Path(hit).is_file():
                return Path(hit)
    return None


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception:
        return None


# ------------------------------------------------------------- chat backends
#
# A backend is anything with .name, .detail and .stream(message, history) ->
# iterator of text chunks. Keeping the contract this small is what lets the same
# app drive a local HTTP service, a CLI, or the built-in stub.


class BackendError(RuntimeError):
    pass


def render_history(history, turns):
    """Flatten the transcript into plain text.

    Passing the conversation in the prompt rather than relying on the backend's
    own session handling keeps this working across CLI versions and endpoints
    that are stateless.
    """
    recent = [m for m in history if m.get("role") in ("user", "assistant")][-turns:]
    lines = []
    for msg in recent:
        who = "User" if msg["role"] == "user" else "Aster"
        text = (msg.get("text") or "").strip()
        if text:
            lines.append(f"{who}: {text}")
    return "\n\n".join(lines)


# ------------------------------------------------------ discovering Aster
#
# Read-only: fetch Aster's own page, read the calls its front end makes, and
# report them. This never POSTs anything while probing - guessing at unknown
# endpoints could trip something with side effects.

CALL_RES = [
    ("fetch", re.compile(r"""(?:fetch|axios\.\w+|\$\.(?:post|get|ajax))\s*\(\s*['"`]([^'"`\s]+)""")),
    ("ws", re.compile(r"""new\s+WebSocket\s*\(\s*['"`]([^'"`\s]+)""")),
    ("sse", re.compile(r"""new\s+EventSource\s*\(\s*['"`]([^'"`\s]+)""")),
]
SCRIPT_SRC_RE = re.compile(r"""<script[^>]+src\s*=\s*['"]([^'"]+)['"]""", re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
ASSET_SUFFIXES = (".js", ".css", ".png", ".jpg", ".svg", ".ico", ".webmanifest", ".map", ".woff", ".woff2")
# Endpoint names that look like "this is where the chat goes".
CHATTY = ("chat", "message", "msg", "send", "ask", "say", "prompt", "completion", "talk", "reply")


def _fetch_text(url, timeout=4, limit=800_000):
    req = urllib.request.Request(url, headers={"User-Agent": "aster-app/probe"})
    with local_opener().open(req, timeout=timeout) as resp:
        ctype = resp.headers.get("Content-Type", "")
        return resp.read(limit).decode("utf-8", "replace"), ctype


def discover_aster(base, timeout=4):
    """Scrape Aster's web UI for the endpoint it talks to.

    Returns {"base", "ok", "title", "error", "candidates": [{url, kind, hint}]}.
    """
    base = (base or "").rstrip("/")
    out = {"base": base, "ok": False, "title": None, "error": None, "candidates": []}
    if not base:
        out["error"] = "no asterUrl configured"
        return out

    try:
        page, _ = _fetch_text(base + "/", timeout)
    except Exception as exc:
        out["error"] = f"{exc}"
        return out
    out["ok"] = True
    title = TITLE_RE.search(page)
    if title:
        out["title"] = " ".join(title.group(1).split())[:60]

    # Bounded overall: the app autostarts at logon and must not hang here if
    # Aster is up but wedged.
    deadline = time.monotonic() + 3 * timeout
    sources = [page]
    for src in SCRIPT_SRC_RE.findall(page)[:6]:
        if time.monotonic() > deadline:
            break
        if src.startswith(("http://", "https://")) and not src.startswith(base):
            continue  # same-origin only; a CDN bundle isn't Aster's API
        try:
            body, _ = _fetch_text(urllib.parse.urljoin(base + "/", src), timeout)
            sources.append(body)
        except Exception:
            continue

    seen = set()
    for body in sources:
        for kind, pattern in CALL_RES:
            for raw in pattern.findall(body):
                if "${" in raw or raw.startswith(("data:", "blob:")):
                    continue
                url = urllib.parse.urljoin(base + "/", raw)
                if not url.startswith(("http://", "https://", "ws://", "wss://")):
                    continue
                path = urllib.parse.urlparse(url).path
                if path.lower().endswith(ASSET_SUFFIXES):
                    continue
                if url in seen:
                    continue
                seen.add(url)
                out["candidates"].append({"url": url, "kind": kind, "path": path})

    # Most chat-looking first, so the top entry is the one worth wiring.
    def rank(cand):
        low = cand["path"].lower()
        return (
            0 if any(w in low for w in CHATTY) else 1,
            0 if cand["kind"] == "fetch" else 1,
            len(low),
        )

    out["candidates"].sort(key=rank)
    return out


def best_chat_endpoint(found):
    """The one candidate worth auto-wiring, or None if it's ambiguous."""
    for cand in found.get("candidates") or []:
        if cand["kind"] == "fetch" and any(w in cand["path"].lower() for w in CHATTY):
            return cand
    return None


class EchoBackend:
    """Works with zero setup, so the phone side can be tested before wiring Aster."""

    name = "echo"

    def __init__(self, config, system):
        self.config = config
        self.system = system
        self.detail = "built-in stub - no real Aster wired up yet"

    def stream(self, message, history):
        wants_art = re.search(
            r"\b(draw|render|paint|picture|image|sketch|portrait)\b", message, re.I
        )
        yield (
            "I'm the built-in stub, not the real Aster - no chat backend is wired "
            "up yet. Point `http.url` at Aster's endpoint, or set `cli.command`, "
            "in aster.config.json (see the README).\n\n"
            f"You said: {message.strip()[:400]}"
        )
        if wants_art:
            yield (
                "\n\nRendering is separate from chat, so this part does work:\n\n"
                '```render\n{"prompt": "'
                + message.strip().replace('"', "'")[:180]
                + '", "aspect": "portrait"}\n```'
            )


class HttpBackend:
    """Aster already listens on a port. OpenAI-shaped or a plain {message} POST."""

    name = "http"

    def __init__(self, config, system):
        self.cfg = config["http"]
        self.system = system
        self.url = self.cfg["url"]
        style = self.cfg.get("style") or "auto"
        if style == "auto":
            style = "openai" if "chat/completions" in self.url else "simple"
        self.style = style
        self.detail = f"{self.url} ({self.style})"

    def stream(self, message, history):
        if self.style == "openai":
            payload = {
                "model": self.cfg.get("model") or "aster",
                "messages": (
                    [{"role": "system", "content": self.system}]
                    + [
                        {"role": m["role"], "content": m.get("text") or ""}
                        for m in history
                        if m.get("role") in ("user", "assistant")
                    ]
                    + [{"role": "user", "content": message}]
                ),
                "stream": False,
            }
        else:
            payload = {
                "message": message,
                "system": self.system,
                "history": [
                    {"role": m["role"], "text": m.get("text") or ""}
                    for m in history
                    if m.get("role") in ("user", "assistant")
                ],
            }

        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        headers.update(self.cfg.get("headers") or {})
        req = urllib.request.Request(self.url, data=body, headers=headers)
        try:
            with local_opener().open(req, timeout=self.cfg.get("timeoutSeconds", 300)) as resp:
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise BackendError(f"Aster returned HTTP {exc.code}: {detail}") from None
        except Exception as exc:
            raise BackendError(f"Could not reach Aster at {self.url}: {exc}") from None

        yield self._extract(raw)

    @staticmethod
    def _extract(raw):
        try:
            data = json.loads(raw)
        except Exception:
            return raw.strip()  # a plain-text endpoint is fine too
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    msg = first.get("message")
                    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                        return msg["content"]
                    if isinstance(first.get("text"), str):
                        return first["text"]
            for key in ("reply", "text", "content", "response", "output", "message"):
                val = data.get(key)
                if isinstance(val, str):
                    return val
        return json.dumps(data)[:2000]


class CliBackend:
    """Spawn a command per turn: prompt in on stdin, reply out on stdout.

    Defaults to the Claude Code CLI in print mode. Deliberately no
    auto-approve flag - a phone-driven agent with blanket tool permissions on
    the home PC is not a default anyone should get by accident. Renders don't
    need it: they go through this server's own ComfyUI client.
    """

    name = "cli"

    def __init__(self, config, system):
        self.cfg = config["cli"]
        self.system = system
        self.command = self.cfg.get("command") or detect_claude_cli()
        if not self.command:
            raise BackendError("No CLI command configured and no `claude` on PATH")
        if isinstance(self.command, str):
            self.command = [self.command]
        # Resolve now, not on the first message, so --probe can say it's broken.
        exe = self.command[0]
        if not (os.path.isfile(exe) or shutil.which(exe)):
            raise BackendError(f"command not found: {exe}")
        self.cwd = self.cfg.get("cwd") or str(HERE.parent.parent)
        self.detail = " ".join(self.command) + f"  (cwd {self.cwd})"

    def _compose(self, message, history):
        parts = [self.system]
        if self.cfg.get("includeHistory", True):
            past = render_history(history, int(self.cfg.get("historyTurns", 12)))
            if past:
                parts.append("--- conversation so far ---\n" + past + "\n--- end ---")
        parts.append("User: " + message.strip())
        parts.append("Reply as Aster.")
        return "\n\n".join(parts)

    def stream(self, message, history):
        prompt = self._compose(message, history)
        try:
            proc = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.cwd if os.path.isdir(self.cwd) else None,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except FileNotFoundError:
            raise BackendError(f"Command not found: {self.command[0]}") from None

        timeout = float(self.cfg.get("timeoutSeconds", 300))
        killed = threading.Event()

        def on_timeout():
            killed.set()
            proc.kill()

        timer = threading.Timer(timeout, on_timeout)
        timer.start()
        got_output = False
        try:
            try:
                proc.stdin.write(prompt)
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass  # some CLIs read argv only; let stdout/stderr explain
            for line in proc.stdout:
                got_output = True
                yield line
            proc.wait()
        finally:
            timer.cancel()

        if got_output:
            if killed.is_set():
                # Say so rather than passing off a truncated reply as complete.
                yield f"\n\n[cut off - Aster hit the {int(timeout)}s timeout]"
            return

        err = (proc.stderr.read() or "").strip()
        if killed.is_set():
            raise BackendError(f"Aster timed out after {int(timeout)}s with no output")
        raise BackendError(
            f"`{self.command[0]}` produced no output (exit {proc.returncode})."
            + (f"\n{err[:800]}" if err else "")
        )


def describe_discovery(found):
    """One line on why discovery didn't produce a usable endpoint."""
    if not found.get("ok"):
        return f"nothing answering at {found['base']} ({found.get('error')})"
    cands = found.get("candidates") or []
    if not cands:
        return f"{found['base']} answered but its page makes no visible API calls"
    kinds = {c["kind"] for c in cands}
    if kinds <= {"ws", "sse"}:
        return (
            f"{found['base']} streams over {'/'.join(sorted(kinds))} "
            f"({cands[0]['path']}) - this backend only speaks single-shot JSON"
        )
    return (
        f"{found['base']} has no obviously chat-shaped endpoint; "
        f"closest is {cands[0]['path']} - set http.url to pick one"
    )


def detect_claude_cli():
    """Find the Claude Code CLI, including the MSIX path SSH sessions land on."""
    found = shutil.which("claude") or shutil.which("claude.cmd")
    if found:
        return [found, "-p"]
    for cand in (
        Path(os.path.expanduser("~")) / "claude-remote.cmd",
        Path(os.path.expanduser("~")) / "bin" / "claude.cmd",
        Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "Claude" / "claude.cmd",
    ):
        if cand.is_file():
            return [str(cand), "-p"]
    return None


def build_backend(config, system):
    """Resolve config.backend, falling back to the stub rather than dying."""
    wanted = (config.get("backend") or "auto").lower()
    order = {
        "http": ["http"],
        "cli": ["cli"],
        "echo": ["echo"],
        "auto": ["http", "cli", "echo"],
    }.get(wanted, ["http", "cli", "echo"])

    notes = []
    for kind in order:
        try:
            if kind == "http":
                if not (config["http"].get("url") or "").strip():
                    # Nothing configured: ask Aster's own page where it posts.
                    found = discover_aster(config.get("asterUrl"))
                    best = best_chat_endpoint(found)
                    if best:
                        config = deep_merge(config, {"http": {"url": best["url"]}})
                        backend = HttpBackend(config, system)
                        backend.detail += "  [discovered]"
                        return backend, notes
                    notes.append(f"http: {describe_discovery(found)}")
                    continue
                return HttpBackend(config, system), notes
            if kind == "cli":
                return CliBackend(config, system), notes
            return EchoBackend(config, system), notes
        except BackendError as exc:
            notes.append(f"{kind}: {exc}")
        except Exception as exc:
            notes.append(f"{kind}: {exc}")
    return EchoBackend(config, system), notes


# --------------------------------------------------------------- comfyui


def local_opener():
    """Bypass any configured proxy - these calls are to 127.0.0.1."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Comfy:
    def __init__(self, config):
        self.cfg = config["comfy"]
        self.url = (self.cfg.get("url") or "http://127.0.0.1:8000").rstrip("/")
        self._checkpoints = None

    def _get(self, path, timeout=6):
        req = urllib.request.Request(self.url + path)
        with local_opener().open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace") or "{}")

    def status(self):
        try:
            stats = self._get("/system_stats")
        except Exception as exc:
            return False, f"not reachable at {self.url} ({exc})"
        devices = stats.get("devices") or []
        name = devices[0].get("name") if devices and isinstance(devices[0], dict) else None
        return True, name or self.url

    def checkpoints(self):
        """Cached only on success - the app autostarts at logon and may well be
        up before ComfyUI is, so a failed lookup must not stick."""
        if self._checkpoints:
            return self._checkpoints
        try:
            info = self._get("/object_info/CheckpointLoaderSimple")
            node = info.get("CheckpointLoaderSimple", {})
            opts = node.get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            self._checkpoints = [c for c in opts if isinstance(c, str)]
        except Exception:
            return []
        return self._checkpoints

    def pick_model(self):
        configured = self.cfg.get("model")
        if configured:
            return configured
        names = self.checkpoints()
        if not names:
            up, detail = self.status()
            raise BackendError(
                "ComfyUI reports no checkpoints - is a model installed?"
                if up
                else f"ComfyUI is {detail}"
            )
        # An anime/illustration SDXL suits Aster better than a generic base,
        # same preference order the Kaarten batch uses.
        for hint in ("pony", "illustrious", "noob", "animagine", "anime", "xl"):
            for name in names:
                if hint in name.lower():
                    return name
        return names[0]

    def submit(self, workflow):
        body = json.dumps({"prompt": workflow, "client_id": "aster-app"}).encode("utf-8")
        req = urllib.request.Request(
            self.url + "/prompt", data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with local_opener().open(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace") or "{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise BackendError(f"ComfyUI rejected the workflow: {detail[:600]}") from None
        except Exception as exc:
            raise BackendError(f"Could not queue on ComfyUI: {exc}") from None
        pid = data.get("prompt_id")
        if not pid:
            raise BackendError(f"ComfyUI gave no prompt_id: {json.dumps(data)[:300]}")
        return pid

    def history(self, prompt_id):
        try:
            return self._get(f"/history/{prompt_id}", timeout=10).get(prompt_id)
        except Exception:
            return None

    def queued_ids(self):
        """(running, pending) prompt ids."""
        try:
            data = self._get("/queue", timeout=6)
        except Exception:
            return set(), set()

        def ids(key):
            out = set()
            for entry in data.get(key) or []:
                if isinstance(entry, list) and len(entry) > 1:
                    out.add(entry[1])
            return out

        return ids("queue_running"), ids("queue_pending")

    def view_bytes(self, filename, subfolder=""):
        qs = urllib.parse.urlencode(
            {"filename": filename, "subfolder": subfolder, "type": "output"}
        )
        req = urllib.request.Request(f"{self.url}/view?{qs}")
        with local_opener().open(req, timeout=30) as resp:
            return resp.read(), resp.headers.get("Content-Type", "image/png")


ASPECTS = {
    "portrait": (832, 1216),
    "square": (1024, 1024),
    "landscape": (1216, 832),
}


def default_workflow(model, positive, negative, seed, steps, cfg, width, height,
                     prefix, sampler, scheduler):
    """The stock SDXL text-to-image graph, in ComfyUI's API format."""
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}},
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": prefix, "images": ["8", 0]},
        },
    }


def fill_placeholders(node, values):
    """Substitute %positive%-style placeholders through a workflow override.

    A whole-string match takes the typed value (so %steps% stays an int);
    embedded ones are plain string replacement.
    """
    if isinstance(node, dict):
        return {k: fill_placeholders(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [fill_placeholders(v, values) for v in node]
    if isinstance(node, str):
        exact = node.strip()
        if exact.startswith("%") and exact.endswith("%") and exact[1:-1] in values:
            return values[exact[1:-1]]
        for key, val in values.items():
            token = f"%{key}%"
            if token in node:
                node = node.replace(token, str(val))
        return node
    return node


# ------------------------------------------------------------------ renders


class RenderService:
    def __init__(self, config, comfy):
        self.config = config
        self.comfy = comfy
        self.jobs = []
        self.lock = threading.Lock()
        self._n = 0

    def _prefix(self):
        return self.config["comfy"].get("outputPrefix") or "aster/Aster"

    def compose_prompt(self, text):
        prefix = (self.config.get("renderPrefix") or "").strip()
        text = (text or "").strip()
        if prefix and prefix.lower() not in text.lower():
            return f"{prefix.rstrip(', ')}, {text}" if text else prefix
        return text

    def queue(self, spec, source="manual"):
        """spec: {prompt, negative, aspect|width|height, steps, cfg, seed}."""
        prompt = self.compose_prompt(spec.get("prompt"))
        if not prompt:
            raise BackendError("No prompt to render")

        ccfg = self.config["comfy"]
        aspect = (spec.get("aspect") or "portrait").lower()
        width, height = ASPECTS.get(aspect, ASPECTS["portrait"])
        width = int(spec.get("width") or width)
        height = int(spec.get("height") or height)
        steps = int(spec.get("steps") or ccfg.get("steps") or 30)
        cfg_scale = float(spec.get("cfg") or ccfg.get("cfg") or 6.5)
        seed = spec.get("seed")
        seed = random.randint(1, 2**31 - 1) if seed in (None, "", 0, "0") else int(seed)
        negative = (
            spec.get("negative")
            or self.config.get("renderNegative")
            or DEFAULT_NEGATIVE
        )
        model = self.comfy.pick_model()

        override = ccfg.get("workflow")
        if override:
            raw = read_text(override)
            if not raw:
                raise BackendError(f"Could not read workflow file: {override}")
            workflow = fill_placeholders(
                json.loads(raw),
                {
                    "positive": prompt,
                    "negative": negative,
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "width": width,
                    "height": height,
                    "model": model,
                    "prefix": self._prefix(),
                },
            )
        else:
            workflow = default_workflow(
                model, prompt, negative, seed, steps, cfg_scale, width, height,
                self._prefix(), ccfg.get("sampler") or "dpmpp_2m",
                ccfg.get("scheduler") or "karras",
            )

        prompt_id = self.comfy.submit(workflow)
        with self.lock:
            self._n += 1
            job = {
                "id": f"j{self._n}",
                "promptId": prompt_id,
                "prompt": prompt,
                "model": model,
                "seed": seed,
                "steps": steps,
                "cfg": cfg_scale,
                "size": f"{width}x{height}",
                "status": "queued",
                "images": [],
                "error": None,
                "source": source,
                "created": time.time(),
            }
            self.jobs.append(job)
            self.jobs = self.jobs[-60:]
        return job

    def refresh(self):
        with self.lock:
            pending = [j for j in self.jobs if j["status"] in ("queued", "running")]
        if not pending:
            return
        running, waiting = self.comfy.queued_ids()
        for job in pending:
            pid = job["promptId"]
            entry = self.comfy.history(pid)
            if entry:
                status = (entry.get("status") or {}).get("status_str")
                if status == "error":
                    job["status"] = "error"
                    job["error"] = self._error_text(entry)
                else:
                    job["images"] = self._images(entry)
                    job["status"] = "done" if job["images"] else "error"
                    if not job["images"]:
                        job["error"] = "finished but saved no images"
            elif pid in running:
                job["status"] = "running"
            elif pid in waiting:
                job["status"] = "queued"
            elif time.time() - job["created"] > 30:
                # Gone from the queue with no history: ComfyUI was restarted or
                # the job was cancelled from the desktop UI.
                job["status"] = "error"
                job["error"] = "disappeared from the ComfyUI queue"

    @staticmethod
    def _images(entry):
        out = []
        for node in (entry.get("outputs") or {}).values():
            for img in (node or {}).get("images") or []:
                if img.get("type") not in (None, "output"):
                    continue
                name, sub = img.get("filename"), img.get("subfolder") or ""
                if name:
                    out.append(f"{sub}/{name}" if sub else name)
        return out

    @staticmethod
    def _error_text(entry):
        for msg in (entry.get("status") or {}).get("messages") or []:
            if isinstance(msg, list) and len(msg) > 1 and msg[0] == "execution_error":
                info = msg[1] if isinstance(msg[1], dict) else {}
                bits = [info.get("node_type"), info.get("exception_message")]
                text = " - ".join(b for b in bits if b)
                if text:
                    return text[:400]
        return "ComfyUI reported an execution error"

    def snapshot(self, limit=30):
        self.refresh()
        with self.lock:
            return list(reversed(self.jobs))[:limit]


# ------------------------------------------------------- render directives

FENCE_RE = re.compile(r"```(?:render|aster-render)[ \t]*\r?\n(.*?)```", re.S | re.I)
INLINE_RE = re.compile(r"\[\[[ \t]*render[ \t]*:[ \t]*(.+?)\]\]", re.S | re.I)
MAX_DIRECTIVES = 2


def extract_directives(text):
    """Pull render requests out of Aster's reply. Returns (clean_text, specs)."""
    specs = []

    def take(match):
        body = match.group(1).strip()
        if len(specs) >= MAX_DIRECTIVES or not body:
            return ""
        spec = None
        if body.startswith("{"):
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    spec = parsed
            except Exception:
                # Near-miss JSON (a trailing comma, an unquoted value) is the
                # common failure. Salvage the prompt rather than feeding braces
                # to the sampler.
                salvage = re.search(r'"prompt"\s*:\s*"([^"]*)"', body)
                if salvage:
                    spec = {"prompt": salvage.group(1)}
        if spec is None:
            spec = {"prompt": " ".join(body.split())}
        if (spec.get("prompt") or "").strip():
            specs.append(spec)
        return ""

    clean = FENCE_RE.sub(take, text)
    clean = INLINE_RE.sub(take, clean)
    return re.sub(r"\n{3,}", "\n\n", clean).strip(), specs


# ------------------------------------------------------------------ transcript


class Transcript:
    """Kept on disk so reopening the app on the phone doesn't lose the thread."""

    def __init__(self, path=CHAT_PATH, cap=400):
        self.path = path
        self.cap = cap
        self.lock = threading.Lock()
        self.messages = []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self.messages = [m for m in data if isinstance(m, dict)][-cap:]
        except Exception:
            pass

    def _save(self):
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.messages, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass  # a read-only folder shouldn't take chat down

    def add(self, role, text, jobs=None):
        with self.lock:
            msg = {
                "role": role,
                "text": text,
                "at": time.time(),
                "jobs": jobs or [],
            }
            self.messages.append(msg)
            self.messages = self.messages[-self.cap :]
            self._save()
            return msg

    def history(self):
        with self.lock:
            return list(self.messages)

    def clear(self):
        with self.lock:
            self.messages = []
            self._save()


# ------------------------------------------------------- gallery + png meta
#
# Trimmed from tools/render-gallery/server.py on purpose: each of these tools
# should be a single file you can drop on the PC and run.


def detect_output_dir(explicit=None):
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("COMFY_OUTPUT")
    if env:
        return Path(env).expanduser()
    existing = [p for p in (Path(c).expanduser() for c in OUTPUT_CANDIDATES) if p.is_dir()]
    if not existing:
        return None

    def newest(root):
        best = 0.0
        for path in root.rglob("*"):
            if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file():
                try:
                    best = max(best, path.stat().st_mtime)
                except OSError:
                    pass
        return best

    ranked = max(existing, key=newest)
    return ranked if newest(ranked) else existing[0]


def list_images(root, limit=300):
    out = []
    if not root or not root.is_dir():
        return out
    for path in root.rglob("*"):
        if path.suffix.lower() not in IMAGE_SUFFIXES or not path.is_file():
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        out.append(
            {
                "name": path.relative_to(root).as_posix(),
                "mtime": st.st_mtime,
                "size": st.st_size,
            }
        )
    out.sort(key=lambda d: d["mtime"], reverse=True)
    return out[:limit]


def safe_join(root, rel):
    """Resolve rel under root, refusing anything that escapes it."""
    if not root:
        return None
    rel = urllib.parse.unquote(rel).lstrip("/")
    if not rel:
        return None
    target = (root / rel).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return None
    return target if target.is_file() else None


def png_text_chunks(path, max_bytes=6_000_000):
    """ComfyUI stashes the workflow in the PNG's text chunks."""
    chunks = {}
    try:
        with open(path, "rb") as fh:
            if fh.read(8) != b"\x89PNG\r\n\x1a\n":
                return chunks
            read = 0
            while read < max_bytes:
                head = fh.read(8)
                if len(head) < 8:
                    break
                length, ctype = struct.unpack(">I4s", head)
                if ctype == b"IEND":
                    break
                data = fh.read(length)
                fh.read(4)  # crc
                read += length + 12
                try:
                    if ctype == b"tEXt":
                        key, _, val = data.partition(b"\x00")
                        chunks[key.decode("latin-1")] = val.decode("utf-8", "replace")
                    elif ctype == b"zTXt":
                        key, _, rest = data.partition(b"\x00")
                        chunks[key.decode("latin-1")] = zlib.decompress(rest[1:]).decode(
                            "utf-8", "replace"
                        )
                    elif ctype == b"iTXt":
                        key, _, rest = data.partition(b"\x00")
                        compressed = rest[:1] == b"\x01"
                        body = rest[2:].split(b"\x00", 2)[-1]
                        if compressed:
                            body = zlib.decompress(body)
                        chunks[key.decode("latin-1")] = body.decode("utf-8", "replace")
                except Exception:
                    continue
    except OSError:
        pass
    return chunks


def summarize_workflow(prompt_json):
    try:
        wf = json.loads(prompt_json)
    except Exception:
        return None
    if not isinstance(wf, dict):
        return None

    def text_of(ref):
        if not isinstance(ref, list) or not ref:
            return None
        node = wf.get(str(ref[0]))
        if not isinstance(node, dict):
            return None
        val = node.get("inputs", {}).get("text")
        return val if isinstance(val, str) else None

    info = {}
    for node in wf.values():
        if not isinstance(node, dict):
            continue
        cls = node.get("class_type", "")
        ins = node.get("inputs", {})
        if not isinstance(ins, dict):
            continue
        if "KSampler" in cls:
            for key in ("seed", "noise_seed", "steps", "cfg", "sampler_name", "scheduler"):
                if key in ins and not isinstance(ins[key], list):
                    info["seed" if key == "noise_seed" else key] = ins[key]
            pos, neg = text_of(ins.get("positive")), text_of(ins.get("negative"))
            if pos:
                info["positive"] = pos
            if neg:
                info["negative"] = neg
        elif "CheckpointLoader" in cls and "ckpt_name" in ins:
            info["model"] = ins["ckpt_name"]
        elif "EmptyLatent" in cls:
            for key in ("width", "height"):
                if not isinstance(ins.get(key), list):
                    info[key] = ins.get(key)
    return info or None


def image_meta(path):
    if path.suffix.lower() != ".png":
        return None
    chunks = png_text_chunks(path)
    return summarize_workflow(chunks["prompt"]) if "prompt" in chunks else None


def thumb_bytes(path, box=420):
    if not HAVE_PIL:
        return None
    try:
        st = path.stat()
        cached = THUMB_DIR / f"{abs(hash((str(path), st.st_mtime_ns)))}.jpg"
        if cached.is_file():
            return cached.read_bytes()
        from PIL import Image as PILImage

        THUMB_DIR.mkdir(parents=True, exist_ok=True)
        with PILImage.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((box, box), PILImage.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=82)
        data = buf.getvalue()
        cached.write_bytes(data)
        return data
    except Exception:
        return None


# ---------------------------------------------------------------- app icon


def _png_bytes(size, rgb_rows):
    raw = b"".join(b"\x00" + row for row in rgb_rows)

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def make_star_icon(size=180):
    """The render gallery's gold star, kept pixel-identical so retiring that
    tool doesn't change the tile already sitting on the phone's home screen."""
    import math

    cx = cy = size / 2
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        r = size * 0.40 if i % 2 == 0 else size * 0.16
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))

    def inside(x, y):
        hit = False
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                hit = not hit
            j = i
        return hit

    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            d = math.hypot(x - cx, y - cy) / (size / 2)
            bg = (max(0, int(26 - d * 8)), max(0, int(19 - d * 6)), max(0, int(56 - d * 14)))
            row += bytes((232, 185, 58)) if inside(x + 0.5, y + 0.5) else bytes(bg)
        rows.append(bytes(row))
    return _png_bytes(size, rows)


def make_icon(size=180):
    """An aster bloom - violet petals, gold centre. Drawn by hand so the icon
    needs no image library, and distinct from the gallery's gold star."""
    import math

    cx = cy = size / 2
    petal_r = size * 0.44
    core_r = size * 0.13
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            dist = math.hypot(dx, dy)
            theta = math.atan2(dy, dx)
            edge = petal_r * (0.42 + 0.58 * abs(math.cos(3 * theta)))
            if dist <= core_r:
                px = (232, 185, 58)
            elif dist <= edge:
                # brighter toward the tips so the petals read at icon size
                t = dist / max(edge, 1e-6)
                px = (
                    int(139 + 78 * t),
                    int(104 + 60 * t),
                    int(232 + 18 * t),
                )
            else:
                d = dist / (size / 2)
                px = (
                    max(0, int(26 - d * 8)),
                    max(0, int(19 - d * 6)),
                    max(0, int(56 - d * 14)),
                )
            row += bytes(tuple(min(255, max(0, c)) for c in px))
        rows.append(bytes(row))
    return _png_bytes(size, rows)


# ---------------------------------------------------------------- front end

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__APPTITLE__</title>
<link rel="manifest" href="__MANIFEST__">
<link rel="apple-touch-icon" href="__APPICON__">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="__APPTITLE__">
<meta name="theme-color" content="#12102a">
<style>
:root{--bg:#12102a;--card:#1c1940;--line:#322d63;--ink:#ece9ff;--dim:#9d97c8;
  --gold:#e8b93a;--violet:#a78bfa;--bad:#ff8a8a}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);overflow:hidden;
  font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
#app{display:flex;flex-direction:column;height:100dvh;
  padding:env(safe-area-inset-top) env(safe-area-inset-right) 0 env(safe-area-inset-left)}
header{flex:none;background:rgba(18,16,42,.94);border-bottom:1px solid #2b2757;padding:10px 14px 0}
.top{display:flex;align-items:baseline;gap:8px}
h1{margin:0;font-size:17px;letter-spacing:.2px}
h1 span{color:var(--violet)}
#status{font-size:11px;color:var(--dim);flex:1;text-align:right;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#status.bad{color:var(--bad)}
nav{display:flex;gap:4px;margin-top:9px}
nav button{flex:1;background:none;border:0;border-bottom:2px solid transparent;
  color:var(--dim);padding:8px 4px 7px;font-size:14px}
nav button.on{color:var(--ink);border-bottom-color:var(--violet)}
main{flex:1;min-height:0;position:relative}
.pane{position:absolute;inset:0;display:none;flex-direction:column;min-height:0}
.pane.on{display:flex}
.scroll{flex:1;min-height:0;overflow-y:auto;-webkit-overflow-scrolling:touch;
  padding:12px 14px calc(14px + env(safe-area-inset-bottom))}
input,textarea,select,button{font-family:inherit}
input,textarea,select{width:100%;background:var(--card);border:1px solid var(--line);
  color:var(--ink);border-radius:9px;padding:9px 11px;font-size:16px}
textarea{resize:none}
.btn{background:var(--violet);border:0;color:#150f2e;border-radius:9px;
  padding:10px 14px;font-size:15px;font-weight:600}
.btn.ghost{background:var(--card);border:1px solid var(--line);color:var(--ink);font-weight:400}
.btn[disabled]{opacity:.5}

/* chat */
#log{display:flex;flex-direction:column;gap:10px}
.msg{max-width:88%;padding:9px 12px;border-radius:14px;white-space:pre-wrap;
  word-break:break-word;overflow-wrap:anywhere}
.msg.you{align-self:flex-end;background:#2a2560;border-bottom-right-radius:5px}
.msg.aster{align-self:flex-start;background:var(--card);border-bottom-left-radius:5px}
.msg.err{align-self:stretch;background:#3a1c2c;border:1px solid #6b2b44;color:#ffd7e0;
  max-width:100%;font-size:13px}
.msg pre{background:#100e26;border:1px solid var(--line);border-radius:8px;
  padding:8px;overflow-x:auto;font-size:12px;margin:6px 0}
.typing{color:var(--dim);font-style:italic}
#composer{flex:none;display:flex;gap:8px;align-items:flex-end;padding:10px 12px;
  padding-bottom:calc(10px + env(safe-area-inset-bottom));
  border-top:1px solid #2b2757;background:rgba(18,16,42,.97)}
#say{max-height:34vh}

/* render cards */
.job{background:var(--card);border:1px solid var(--line);border-radius:12px;
  overflow:hidden;margin-top:8px;max-width:100%}
.job .head{padding:8px 10px;font-size:12px;color:var(--dim);display:flex;gap:8px}
.job .head b{color:var(--violet);font-weight:600;text-transform:uppercase;font-size:10px;
  letter-spacing:.6px;align-self:center}
.job .head .grow{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* capped, or one portrait render fills the whole screen and you scroll past it */
.job img{display:block;width:100%;max-height:52vh;object-fit:contain;background:#221e4d}
.job .why{padding:0 10px 9px;font-size:12px;color:var(--bad)}
.spin{height:4px;background:linear-gradient(90deg,var(--card),var(--violet),var(--card));
  background-size:200% 100%;animation:sweep 1.1s linear infinite}
@keyframes sweep{from{background-position:200% 0}to{background-position:0 0}}

/* render form */
.field{margin-bottom:10px}
.field label{display:block;font-size:12px;color:var(--dim);margin-bottom:4px}
.row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:8px}

/* gallery */
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px}
figure{margin:0;background:var(--card);border-radius:12px;overflow:hidden;position:relative}
figure img{display:block;width:100%;aspect-ratio:3/4;object-fit:cover;background:#221e4d}
figcaption{padding:6px 8px 8px;font-size:11px;color:var(--dim);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fresh::after{content:"new";position:absolute;top:7px;right:7px;background:var(--gold);
  color:#231c02;font-size:10px;font-weight:700;padding:2px 6px;border-radius:6px}
.gbar{display:flex;gap:8px;align-items:center;margin-bottom:10px}
.gbar label{font-size:12px;color:var(--dim);display:flex;align-items:center;gap:5px;flex:none}
.gbar input[type=checkbox]{width:auto;accent-color:var(--violet)}
.hint{color:var(--dim);font-size:13px;padding:24px 6px;text-align:center}

/* lightbox */
#view{position:fixed;inset:0;background:rgba(8,7,20,.97);z-index:20;display:none;
  flex-direction:column;padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}
#view.on{display:flex}
#full{flex:1;min-height:0;width:100%;object-fit:contain}
#meta{max-height:42vh;overflow:auto;padding:10px 14px 16px;font-size:12px;
  border-top:1px solid #2b2757}
#meta b{color:var(--gold);font-weight:600}
#meta .r{color:var(--dim);margin-bottom:6px}
#meta .p{color:var(--ink);white-space:pre-wrap;word-break:break-word}
#close{position:absolute;top:calc(env(safe-area-inset-top) + 8px);right:12px;z-index:21}
</style></head><body>
<div id="app">
<header>
  <div class="top"><h1>Ast<span>er</span></h1><div id="status">connecting…</div></div>
  <nav>
    <button data-tab="chat" class="on">Chat</button>
    <button data-tab="render">Render</button>
    <button data-tab="gallery">Gallery</button>
  </nav>
</header>
<main>
  <section class="pane on" id="pane-chat">
    <div class="scroll" id="chatScroll"><div id="log"></div></div>
    <div id="composer">
      <textarea id="say" rows="1" placeholder="Message Aster…"></textarea>
      <button class="btn" id="send">Send</button>
    </div>
  </section>

  <section class="pane" id="pane-render">
    <div class="scroll">
      <div class="field">
        <label for="rp">Prompt</label>
        <textarea id="rp" rows="4" placeholder="what to draw"></textarea>
      </div>
      <div class="field">
        <label for="rn">Negative <span id="negNote"></span></label>
        <textarea id="rn" rows="2" placeholder="leave blank for the default"></textarea>
      </div>
      <div class="row3 field">
        <div><label for="ra">Aspect</label><select id="ra">
          <option value="portrait">portrait</option>
          <option value="square">square</option>
          <option value="landscape">landscape</option></select></div>
        <div><label for="rs">Steps</label><input id="rs" inputmode="numeric" placeholder="30"></div>
        <div><label for="rc">CFG</label><input id="rc" inputmode="decimal" placeholder="6.5"></div>
      </div>
      <div class="row2 field">
        <div><label for="rseed">Seed</label><input id="rseed" inputmode="numeric" placeholder="random"></div>
        <div style="display:flex;align-items:flex-end">
          <button class="btn" id="queue" style="width:100%">Queue render</button>
        </div>
      </div>
      <div id="jobs"></div>
    </div>
  </section>

  <section class="pane" id="pane-gallery">
    <div class="scroll">
      <div class="gbar">
        <input id="q" placeholder="filter by filename" autocomplete="off">
        <label><input type="checkbox" id="onlyAster" checked>Aster</label>
      </div>
      <div id="count" class="hint" style="padding:0 0 8px;text-align:left"></div>
      <div id="grid"></div>
    </div>
  </section>
</main>
</div>
<div id="view"><button class="btn ghost" id="close">Close</button><img id="full" alt=""><div id="meta"></div></div>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const ago=t=>{const s=Date.now()/1000-t;
  if(s<60)return'just now'; if(s<3600)return Math.floor(s/60)+'m ago';
  if(s<86400)return Math.floor(s/3600)+'h ago'; return Math.floor(s/86400)+'d ago';};
let hello={}, jobs=[], items=[], seen=new Set(), firstList=true, busy=false, prefix='aster/';

/* ---- tabs ---- */
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('on',x===b));
  document.querySelectorAll('.pane').forEach(p=>
    p.classList.toggle('on',p.id==='pane-'+b.dataset.tab));
  if(b.dataset.tab==='gallery') loadList();
  if(b.dataset.tab==='render') loadJobs();
});

/* ---- chat ---- */
function bubble(role,text,cls){
  const d=document.createElement('div');
  d.className='msg '+(cls||(role==='user'?'you':'aster'));
  d.innerHTML=fmt(text);
  $('log').append(d); return d;
}
function fmt(text){
  // just enough markdown for a phone: fenced code, everything else literal
  const parts=String(text==null?'':text).split(/```/);
  return parts.map((p,i)=>i%2 ? '<pre>'+esc(p.replace(/^\\w*\\n/,''))+'</pre>'
                             : esc(p)).join('');
}
function jobCard(job){
  const d=document.createElement('div'); d.className='job'; d.dataset.job=job.id;
  paintCard(d,job); return d;
}
function paintCard(el,job){
  const done=job.status==='done', bad=job.status==='error';
  el.innerHTML='<div class="head"><b>'+esc(job.status)+'</b>'
    +'<span class="grow">'+esc(job.prompt)+'</span></div>'
    +(done?'':bad?'':'<div class="spin"></div>')
    +(done?job.images.map(n=>'<img loading="lazy" src="/img/'+encodeURI(n)+'" alt="">').join(''):'')
    +(bad?'<div class="why">'+esc(job.error||'render failed')+'</div>':'');
  if(done&&job.images.length){
    el.querySelectorAll('img').forEach((img,i)=>img.onclick=()=>openImage(job.images[i]));
  }
}
function scrollDown(){const s=$('chatScroll'); s.scrollTop=s.scrollHeight;}

async function send(){
  const text=$('say').value.trim();
  if(!text||busy) return;
  busy=true; $('send').disabled=true; $('say').value=''; $('say').style.height='';
  bubble('user',text);
  const out=bubble('assistant','…'); out.classList.add('typing');
  scrollDown();
  let acc='';
  try{
    const res=await fetch('/api/chat',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
    if(!res.ok) throw new Error('HTTP '+res.status);
    const frame=obj=>{
      if(obj.delta){acc+=obj.delta; out.classList.remove('typing');
        out.innerHTML=fmt(acc); scrollDown();}
      if(obj.error){out.className='msg err'; out.textContent=obj.error;}
      if(obj.done){
        const m=obj.message||{};
        out.className='msg aster'; out.innerHTML=fmt(m.text||acc||'(no reply)');
        for(const j of (m.newJobs||[])) out.append(jobCard(j));
        if((m.newJobs||[]).length) loadJobs();
        scrollDown();
      }
    };
    const reader=res.body&&res.body.getReader?res.body.getReader():null;
    if(reader){
      const dec=new TextDecoder(); let buf='';
      for(;;){
        const {value,done}=await reader.read(); if(done) break;
        buf+=dec.decode(value,{stream:true});
        let cut;
        while((cut=buf.indexOf('\\n\\n'))>=0){
          const line=buf.slice(0,cut).trim(); buf=buf.slice(cut+2);
          if(line.startsWith('data:')){try{frame(JSON.parse(line.slice(5)));}catch(e){}}
        }
      }
    }else{ // older Safari: no streaming reader, take the whole body
      for(const line of (await res.text()).split('\\n\\n')){
        if(line.trim().startsWith('data:')){try{frame(JSON.parse(line.trim().slice(5)));}catch(e){}}
      }
    }
  }catch(e){ out.className='msg err'; out.textContent='Could not reach the app: '+e.message; }
  busy=false; $('send').disabled=false; scrollDown();
}
$('send').onclick=send;
$('say').addEventListener('input',e=>{
  e.target.style.height='auto'; e.target.style.height=e.target.scrollHeight+'px';});
$('say').addEventListener('keydown',e=>{
  if(e.key==='Enter'&&(e.metaKey||e.ctrlKey)){e.preventDefault();send();}});

async function loadChat(){
  try{
    const msgs=await (await fetch('/api/history',{cache:'no-store'})).json();
    $('log').innerHTML='';
    for(const m of msgs){
      const el=bubble(m.role,m.text);
      for(const id of (m.jobs||[])){
        const job=jobs.find(j=>j.id===id);
        if(job) el.append(jobCard(job));
      }
    }
    if(!msgs.length) bubble('assistant',
      "Aster here — running on the PC. Ask me something, or say what you'd like drawn.");
    scrollDown();
  }catch(e){}
}

/* ---- renders ---- */
async function queue(){
  const prompt=$('rp').value.trim();
  if(!prompt) return;
  $('queue').disabled=true;
  try{
    const res=await fetch('/api/render',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({prompt,negative:$('rn').value.trim(),aspect:$('ra').value,
        steps:$('rs').value.trim(),cfg:$('rc').value.trim(),seed:$('rseed').value.trim()})});
    const data=await res.json();
    if(!res.ok) throw new Error(data.error||('HTTP '+res.status));
    await loadJobs();
  }catch(e){ alert('Render failed: '+e.message); }
  $('queue').disabled=false;
}
$('queue').onclick=queue;

async function loadJobs(){
  try{ jobs=await (await fetch('/api/jobs',{cache:'no-store'})).json(); }catch(e){ return; }
  const box=$('jobs');
  box.innerHTML=jobs.length?'':'<div class="hint">No renders yet.</div>';
  for(const j of jobs) box.append(jobCard(j));
  // keep any cards already sitting inside chat bubbles in sync
  for(const j of jobs)
    document.querySelectorAll('#log .job[data-job="'+j.id+'"]').forEach(el=>paintCard(el,j));
  return jobs;
}
setInterval(()=>{ if(jobs.some(j=>j.status==='queued'||j.status==='running')) loadJobs(); },3000);

/* ---- gallery ---- */
function drawGrid(){
  const f=$('q').value.trim().toLowerCase(), only=$('onlyAster').checked;
  const show=items.filter(i=>(!f||i.name.toLowerCase().includes(f))
    &&(!only||i.name.toLowerCase().startsWith(prefix)));
  $('count').textContent=show.length+' image'+(show.length===1?'':'s')
    +(only?' in '+prefix:'');
  $('grid').innerHTML='';
  for(const i of show){
    const fig=document.createElement('figure');
    if(i.fresh) fig.className='fresh';
    const img=document.createElement('img');
    img.loading='lazy'; img.src='/thumb/'+encodeURI(i.name); img.alt=i.name;
    img.onclick=()=>openImage(i.name);
    const cap=document.createElement('figcaption');
    cap.textContent=i.name.split('/').pop()+' · '+ago(i.mtime);
    fig.append(img,cap); $('grid').append(fig);
  }
}
async function loadList(){
  try{
    const list=await (await fetch('/api/list',{cache:'no-store'})).json();
    for(const i of list) i.fresh = !firstList && !seen.has(i.name);
    items=list; list.forEach(i=>seen.add(i.name)); firstList=false; drawGrid();
  }catch(e){}
}
$('q').oninput=drawGrid; $('onlyAster').onchange=drawGrid;
// same 8s cadence as the standalone gallery, but only while you're looking at it
const onGallery=()=>$('pane-gallery').classList.contains('on');
setInterval(()=>{ if(onGallery() && !document.hidden) loadList(); },8000);

async function openImage(name){
  $('full').src='/img/'+encodeURI(name);
  $('meta').innerHTML='<div class="r">'+esc(name)+'</div>';
  $('view').classList.add('on');
  try{
    const m=await (await fetch('/api/meta/'+encodeURI(name))).json();
    const bits=[];
    if(m.model) bits.push('<div class="r"><b>model</b> '+esc(m.model)+'</div>');
    const s=[]; for(const k of ['seed','steps','cfg','sampler_name','scheduler'])
      if(m[k]!==undefined) s.push(k+' '+m[k]);
    if(m.width&&m.height) s.unshift(m.width+'x'+m.height);
    if(s.length) bits.push('<div class="r">'+esc(s.join(' · '))+'</div>');
    if(m.positive) bits.push('<div class="r"><b>prompt</b></div><div class="p">'+esc(m.positive)+'</div>');
    $('meta').innerHTML='<div class="r">'+esc(name)+'</div>'
      +(bits.length?bits.join(''):'<div class="r">no workflow metadata</div>');
  }catch(e){}
}
$('close').onclick=()=>{$('view').classList.remove('on'); $('full').src='';};

/* ---- boot ---- */
async function loadHello(){
  try{ hello=await (await fetch('/api/hello',{cache:'no-store'})).json(); }
  catch(e){ $('status').textContent='app unreachable'; $('status').className='bad'; return; }
  prefix=(hello.outputPrefix||'aster/Aster').split('/')[0].toLowerCase()+'/';
  const bits=['chat: '+hello.backend, hello.comfy.up?'gpu: ok':'gpu: down'];
  $('status').textContent=bits.join('  ·  ');
  $('status').className=(hello.backend==='echo'||!hello.comfy.up)?'bad':'';
  $('status').title=(hello.backendDetail||'')+'\\n'+(hello.comfy.detail||'');
  if(hello.negativeSource) $('negNote').textContent='(default: '+hello.negativeSource+')';
  $('rs').placeholder=hello.comfy.steps; $('rc').placeholder=hello.comfy.cfg;
}
// One server, two installable icons: "/" opens on Chat, "/gallery" opens on the
// grid. Lets the standalone render gallery retire without losing its tile.
const INIT_TAB='__INITTAB__';
(async()=>{
  await loadHello(); await loadJobs(); await loadChat();
  if(INIT_TAB!=='chat'){
    const btn=document.querySelector('nav button[data-tab="'+INIT_TAB+'"]');
    if(btn) btn.click();
  }
})();
document.addEventListener('visibilitychange',()=>{
  if(document.hidden) return;
  loadHello(); loadJobs(); if(onGallery()) loadList();
});
</script></body></html>
"""


# ------------------------------------------------------------------- server


ENTRY_POINTS = {
    # path -> (title, tab the page opens on, icon route, manifest route)
    "chat": ("Aster", "chat", "/icon.png", "/manifest.webmanifest"),
    "gallery": ("Renders", "gallery", "/icon-gallery.png", "/gallery.webmanifest"),
}


def render_page(entry="chat"):
    title, tab, icon, manifest = ENTRY_POINTS.get(entry, ENTRY_POINTS["chat"])
    return (
        PAGE.replace("__APPTITLE__", title)
        .replace("__APPICON__", icon)
        .replace("__MANIFEST__", manifest)
        .replace("__INITTAB__", tab)
    )


def manifest_for(entry):
    title, _, icon, _ = ENTRY_POINTS[entry]
    return {
        "name": "Aster" if entry == "chat" else "ComfyUI renders",
        "short_name": title,
        "start_url": "/" if entry == "chat" else "/gallery",
        "scope": "/",
        "display": "standalone",
        "background_color": "#12102a",
        "theme_color": "#12102a",
        "icons": [
            {"src": icon, "sizes": "180x180", "type": "image/png"},
            {"src": icon, "sizes": "512x512", "type": "image/png"},
        ],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "AsterApp/1.0"
    app = None  # set to an App instance before serving

    def log_message(self, fmt, *args):
        pass  # quiet: this shares a terminal with the user

    # ---- plumbing

    def _send(self, body, ctype, cache=None, code=200, extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if cache:
            self.send_header("Cache-Control", cache)
        for key, val in (extra or {}).items():
            self.send_header(key, val)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200, cache="no-store"):
        self._send(json.dumps(obj), "application/json", cache, code)

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if length <= 0 or length > 1_000_000:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8", "replace")) or {}
        except Exception:
            return {}

    def _query(self):
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

    def _authed(self):
        token = self.app.token
        if not token:
            return True
        given = self.headers.get("X-Aster-Token")
        if not given:
            for part in (self.headers.get("Cookie") or "").split(";"):
                key, _, val = part.strip().partition("=")
                if key == "aster":
                    given = val
                    break
        if not given:
            given = (self._query().get("t") or [""])[0]
        return bool(given) and hmac.compare_digest(given, token)

    # ---- routes

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = posixpath.normpath(urllib.parse.urlparse(self.path).path)
        app = self.app

        # Unauthenticated: icons and manifests, so the home-screen tiles work.
        if path in ("/icon.png", "/favicon.ico"):
            return self._send(make_icon(), "image/png", "max-age=86400")
        if path == "/icon-gallery.png":
            return self._send(make_star_icon(), "image/png", "max-age=86400")
        if path in ("/manifest.webmanifest", "/gallery.webmanifest"):
            entry = "gallery" if path.startswith("/gallery") else "chat"
            return self._send(
                json.dumps(manifest_for(entry)),
                "application/manifest+json",
                "max-age=3600",
            )

        if path in ("/", "/gallery") and app.token:
            # ?t=<token> once, then a cookie carries it - so <img> tags work too.
            # Both entry points accept it; each redirects back to itself.
            given = (self._query().get("t") or [""])[0]
            if given and hmac.compare_digest(given, app.token):
                return self._send(
                    "",
                    "text/plain",
                    code=302,
                    extra={
                        "Location": path,
                        "Set-Cookie": f"aster={app.token}; Path=/; Max-Age=31536000; SameSite=Lax",
                    },
                )

        if not self._authed():
            return self._send(
                "<h3>Aster</h3><p>Open the full URL with the <code>?t=</code> token "
                "on it. The server printed it at startup; it's also in "
                "<code>aster.token</code> next to server.py.</p>",
                "text/html; charset=utf-8",
                code=401,
            )

        if path in ("/", "/gallery"):
            entry = "gallery" if path == "/gallery" else (
                (self._query().get("tab") or ["chat"])[0]
            )
            return self._send(render_page(entry), "text/html; charset=utf-8", "no-cache")

        if path == "/api/hello":
            up, detail = app.comfy.status()
            return self._json(
                {
                    "backend": app.backend.name,
                    "backendDetail": getattr(app.backend, "detail", ""),
                    "backendNotes": app.backend_notes,
                    "comfy": {
                        "up": up,
                        "detail": detail,
                        "url": app.comfy.url,
                        "steps": app.config["comfy"].get("steps") or 30,
                        "cfg": app.config["comfy"].get("cfg") or 6.5,
                    },
                    "outputPrefix": app.config["comfy"].get("outputPrefix") or "aster/Aster",
                    "outputDir": str(app.output_dir) if app.output_dir else None,
                    "negativeSource": app.negative_source,
                    "renderPrefix": bool(app.config.get("renderPrefix")),
                    "thumbnails": HAVE_PIL,
                }
            )

        if path == "/api/history":
            return self._json(app.transcript.history())

        if path == "/api/jobs":
            return self._json(app.renders.snapshot())

        if path == "/api/list":
            return self._json(list_images(app.output_dir))

        if path.startswith("/api/meta/"):
            target = safe_join(app.output_dir, path[len("/api/meta/") :])
            if not target:
                return self._json({}, code=404)
            return self._json(image_meta(target) or {}, cache="max-age=600")

        if path.startswith("/img/") or path.startswith("/thumb/"):
            return self._serve_image(path)

        return self._send("not found", "text/plain", code=404)

    def do_POST(self):
        path = posixpath.normpath(urllib.parse.urlparse(self.path).path)
        if not self._authed():
            return self._json({"error": "unauthorized"}, code=401)
        if path == "/api/chat":
            return self._chat()
        if path == "/api/render":
            return self._render()
        if path == "/api/reset":
            self.app.transcript.clear()
            return self._json({"ok": True})
        return self._json({"error": "not found"}, code=404)

    # ---- handlers

    def _serve_image(self, path):
        rel = path.split("/", 2)[2]
        want_thumb = path.startswith("/thumb/")
        target = safe_join(self.app.output_dir, rel)

        if target:
            if want_thumb:
                data = thumb_bytes(target)
                if data is not None:
                    return self._send(data, "image/jpeg", "max-age=86400")
            ctype = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
            }.get(target.suffix.lower(), "application/octet-stream")
            try:
                return self._send(target.read_bytes(), ctype, "max-age=86400")
            except OSError:
                return self._send("unreadable", "text/plain", code=500)

        # Not under the folder we detected - ask ComfyUI for it instead, so a
        # misdetected output dir doesn't leave fresh renders invisible. Don't
        # hand a traversal upstream just because it missed locally.
        rel = urllib.parse.unquote(rel).replace("\\", "/").lstrip("/")
        if ".." in rel.split("/"):
            return self._send("not found", "text/plain", code=404)
        sub, _, name = rel.rpartition("/")
        try:
            data, ctype = self.app.comfy.view_bytes(name, sub)
        except Exception:
            return self._send("not found", "text/plain", code=404)
        return self._send(data, ctype, "max-age=86400")

    def _sse_open(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

    def _sse(self, obj):
        self.wfile.write(b"data: " + json.dumps(obj).encode("utf-8") + b"\n\n")
        self.wfile.flush()

    def _chat(self):
        app = self.app
        text = (self._body().get("text") or "").strip()
        if not text:
            return self._json({"error": "empty message"}, code=400)

        history = app.transcript.history()
        app.transcript.add("user", text)
        self._sse_open()

        reply = ""
        try:
            for chunk in app.backend.stream(text, history):
                if not chunk:
                    continue
                reply += chunk
                self._sse({"delta": chunk})
        except BackendError as exc:
            app.transcript.add("assistant", f"[error] {exc}")
            return self._sse({"error": str(exc)})
        except (BrokenPipeError, ConnectionError):
            return  # phone walked away mid-reply
        except Exception as exc:
            app.transcript.add("assistant", f"[error] {exc}")
            return self._sse({"error": f"{type(exc).__name__}: {exc}"})

        clean, specs = extract_directives(reply)
        new_jobs, notes = [], []
        for spec in specs:
            try:
                new_jobs.append(app.renders.queue(spec, source="chat"))
            except BackendError as exc:
                notes.append(str(exc))

        text_out = clean or reply.strip()
        if notes:
            text_out = (text_out + "\n\n[render failed] " + "; ".join(notes)).strip()
        msg = app.transcript.add("assistant", text_out, jobs=[j["id"] for j in new_jobs])

        try:
            self._sse({"done": True, "message": dict(msg, newJobs=new_jobs)})
        except (BrokenPipeError, ConnectionError):
            pass

    def _render(self):
        try:
            job = self.app.renders.queue(self._body(), source="manual")
        except BackendError as exc:
            return self._json({"error": str(exc)}, code=502)
        except Exception as exc:
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, code=500)
        return self._json(job)


# --------------------------------------------------------------------- app


class App:
    def __init__(self, args):
        self.config, config_error = load_config()
        self.config_error = config_error

        if args.comfy:
            self.config["comfy"]["url"] = args.comfy
        if getattr(args, "aster", None):
            self.config["asterUrl"] = args.aster
        if args.backend:
            self.config["backend"] = args.backend

        prompt_file, sheet_file = find_character_files()
        sheet = self.config.get("designSheet")
        self.sheet_file = Path(sheet).expanduser() if _is_path(sheet) else sheet_file

        # renderPrefix / renderNegative each accept a path or the text itself.
        # Anything set in the config wins over what auto-detection found.
        self.prompt_file, self.config["renderPrefix"] = self._resolve_text(
            self.config.get("renderPrefix"), prompt_file
        )
        neg_file, self.config["renderNegative"] = self._resolve_text(
            self.config.get("renderNegative"), find_negative_file()
        )
        if neg_file:
            self.negative_source = neg_file.name
        elif self.config["renderNegative"]:
            self.negative_source = "config"
        else:
            self.negative_source = "built-in"

        self.output_dir = detect_output_dir(args.dir)
        if self.output_dir:
            self.output_dir = self.output_dir.resolve()

        self.comfy = Comfy(self.config)
        self.renders = RenderService(self.config, self.comfy)
        self.transcript = Transcript()

        comfy_up, _ = self.comfy.status()
        self.backend, self.backend_notes = build_backend(
            self.config, self.system_prompt(comfy_up)
        )
        self.token = resolve_token(args)

    @staticmethod
    def _resolve_text(configured, fallback_file):
        """-> (file it came from or None, the text). A config path is read; a
        config string is taken literally; otherwise the detected file is used."""
        if _is_path(configured):
            path = Path(configured).expanduser()
            return path, (read_text(path) or "")
        if isinstance(configured, str) and configured.strip():
            return None, configured.strip()
        if fallback_file:
            return fallback_file, (read_text(fallback_file) or "")
        return None, None

    def system_prompt(self, comfy_up):
        base = (self.config.get("systemPrompt") or DEFAULT_SYSTEM).strip()
        parts = [base]
        sheet = read_text(self.sheet_file) if self.sheet_file else None
        if sheet:
            parts.append(
                "Aster's design sheet, for reference when describing or drawing her:\n\n"
                + sheet[:6000]
            )
        if comfy_up:
            parts.append(RENDER_PROTOCOL.strip())
        return "\n\n".join(parts)


def _is_path(value):
    return isinstance(value, str) and value.strip() and os.path.exists(
        os.path.expanduser(value)
    )


def resolve_token(args):
    if args.no_token:
        return None
    if args.token:
        return args.token
    existing = read_text(TOKEN_PATH)
    if existing:
        return existing
    token = secrets.token_urlsafe(16)
    try:
        TOKEN_PATH.write_text(token, encoding="utf-8")
    except OSError:
        pass
    return token


def lan_hints(port):
    urls = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127."):
                continue
            entry = (ip, ip.startswith("100."))
            if entry not in urls:
                urls.append(entry)
    except OSError:
        pass
    urls.sort(key=lambda e: not e[1])  # tailscale first
    return urls


def probe(app):
    print("Aster app - probe (nothing was started)\n")
    print(f"config      : {CONFIG_PATH if CONFIG_PATH.is_file() else 'none (using defaults)'}")
    if app.config_error:
        print(f"  ! {app.config_error}")
    print(f"chat backend: {app.backend.name} - {getattr(app.backend, 'detail', '')}")
    for note in app.backend_notes:
        print(f"  skipped {note}")
    if app.backend.name == "echo":
        print("  -> no real Aster wired up. Set http.url or cli.command in")
        print("     aster.config.json (copy aster.config.example.json).")

    found = discover_aster(app.config.get("asterUrl"))
    print(f"\naster web UI: {found['base']}")
    if found["ok"]:
        print(f"  answered   : yes{'  - ' + found['title'] if found['title'] else ''}")
        if found["candidates"]:
            print("  calls its page makes (best guess first):")
            for cand in found["candidates"][:8]:
                print(f"    [{cand['kind']:5}] {cand['url']}")
            best = best_chat_endpoint(found)
            print(f"  chat endpoint: {best['url'] if best else 'ambiguous - set http.url yourself'}")
        else:
            print("  no API calls visible in the page or its scripts")
    else:
        print(f"  answered   : no ({found['error']})")
    print()

    claude = detect_claude_cli()
    print(f"claude CLI  : {' '.join(claude) if claude else 'not found on PATH'}")

    up, detail = app.comfy.status()
    print(f"comfyui     : {'up - ' + detail if up else detail}")
    if up:
        names = app.comfy.checkpoints()
        print(f"  checkpoints: {len(names)}")
        for name in names[:8]:
            print(f"    {name}")
        if names:
            try:
                print(f"  would use  : {app.comfy.pick_model()}")
            except BackendError as exc:
                print(f"  ! {exc}")
    print(f"output dir  : {app.output_dir or 'not found - pass --dir'}")
    if app.output_dir:
        print(f"  images     : {len(list_images(app.output_dir))}")
    print(f"thumbnails  : {'Pillow' if HAVE_PIL else 'off (Pillow not importable)'}")
    print(f"aster prompt: {app.prompt_file or 'none found'}")
    print(f"design sheet: {app.sheet_file or 'none found'}")
    print(f"negative    : {app.negative_source}")
    print(f"token       : {'on - ' + str(TOKEN_PATH) if app.token else 'DISABLED'}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Phone app for Aster on the PC")
    ap.add_argument("--port", type=int, default=8778)
    ap.add_argument("--host", default="0.0.0.0", help="default 0.0.0.0 so the phone can reach it")
    ap.add_argument("--dir", help="ComfyUI output folder (default: auto-detect)")
    ap.add_argument("--comfy", help="ComfyUI base URL (default http://127.0.0.1:8000)")
    ap.add_argument("--aster", help="Aster's web UI (default http://127.0.0.1:8787)")
    ap.add_argument("--backend", choices=["auto", "http", "cli", "echo"])
    ap.add_argument("--token", help="shared secret (default: generated into aster.token)")
    ap.add_argument("--no-token", action="store_true", help="serve with no auth at all")
    ap.add_argument("--probe", action="store_true", help="report what's reachable, start nothing")
    ap.add_argument("--log", help="append output here (autostart runs with no console)")
    args = ap.parse_args()

    if args.log:
        # pythonw.exe has no console, so without this a crash leaves no trace.
        stream = open(args.log, "a", buffering=1, encoding="utf-8", errors="replace")
        sys.stdout = sys.stderr = stream
        print(f"\n--- started {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    app = App(args)
    if args.probe:
        return probe(app)

    Handler.app = app
    srv = ThreadingHTTPServer((args.host, args.port), Handler)

    if app.config_error:
        print(f"! {app.config_error}")
    print(f"chat backend : {app.backend.name} - {getattr(app.backend, 'detail', '')}")
    if app.backend.name == "echo":
        print("  no real Aster wired up yet - chat will answer with the stub.")
        print("  run with --probe for details, or see the README.")
    up, detail = app.comfy.status()
    print(f"comfyui      : {'up - ' + detail if up else detail}")
    print(f"output dir   : {app.output_dir or 'not found (pass --dir)'}")
    print(f"thumbnails   : {'Pillow' if HAVE_PIL else 'off (Pillow not installed)'}")

    query = f"?t={app.token}" if app.token else ""
    hints = lan_hints(args.port)
    print("\nOpen on the phone:")
    for ip, is_tailscale in hints or [("localhost", False)]:
        tag = "  (tailscale)" if is_tailscale else ""
        print(f"  http://{ip}:{args.port}/{query}{tag}")
    print("\nOr pin a second icon that opens straight to the renders grid:")
    for ip, is_tailscale in hints or [("localhost", False)]:
        tag = "  (tailscale)" if is_tailscale else ""
        print(f"  http://{ip}:{args.port}/gallery{query}{tag}")
    if app.token:
        print(f"\nToken is stored in {TOKEN_PATH} - the link sets a cookie, so you")
        print("only need the ?t= part once per phone. --no-token turns auth off.")
    else:
        print("\n! Running with NO auth. Keep this on Tailscale only.")
    print("Then Add to Home Screen. Ctrl-C to stop.")

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
