#!/usr/bin/env python3
"""Read-only phone gallery for ComfyUI renders.

Serves the newest images from ComfyUI's output folder as a mobile-friendly
grid you can pin to a phone home screen. Stdlib only - no pip install.
Pillow is used for thumbnails if present, otherwise full images are sent.

    python server.py                       # auto-detect output folder
    python server.py --dir D:\\Comfy\\output --port 8777

Then browse to http://<tailscale-ip>:8777 and Add to Home Screen.
"""

import argparse
import io
import json
import os
import posixpath
import socket
import struct
import sys
import tempfile
import time
import urllib.parse
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
THUMB_DIR = Path(tempfile.gettempdir()) / "comfy-gallery-thumbs"

CANDIDATE_DIRS = [
    "~/Documents/ComfyUI/output",  # ComfyUI Desktop's default
    r"C:\Users\GH-DA\ComfyUI-Shared\output",
    r"C:\Users\GH-DA\ComfyUI-Installs\ComfyUI\ComfyUI\output",
    r"C:\Users\GH-DA\ComfyUI\output",
    "~/ComfyUI/output",
    "./output",
]

try:
    from PIL import Image  # noqa: F401

    HAVE_PIL = True
except Exception:
    HAVE_PIL = False


# ---------------------------------------------------------------- output dir


def newest_image_mtime(root):
    newest = 0.0
    for path in root.rglob("*"):
        if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file():
            try:
                newest = max(newest, path.stat().st_mtime)
            except OSError:
                pass
    return newest


def detect_output_dir():
    """Pick the candidate holding the most recent render.

    A machine can easily carry several ComfyUI installs, and picking the first
    folder that merely exists lands on an empty one. Freshest content wins.
    """
    env = os.environ.get("COMFY_OUTPUT")
    if env:
        return Path(env).expanduser()
    existing = [p for p in (Path(c).expanduser() for c in CANDIDATE_DIRS) if p.is_dir()]
    if not existing:
        return None
    best = max(existing, key=newest_image_mtime)
    return best if newest_image_mtime(best) else existing[0]


def list_images(root, limit=300):
    """Newest-first list of images under root, including subfolders."""
    out = []
    for path in root.rglob("*"):
        if path.suffix.lower() not in IMAGE_SUFFIXES or not path.is_file():
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        out.append({"name": rel, "mtime": st.st_mtime, "size": st.st_size})
    out.sort(key=lambda d: d["mtime"], reverse=True)
    return out[:limit]


def safe_join(root, rel):
    """Resolve rel under root, refusing anything that escapes it."""
    rel = urllib.parse.unquote(rel).lstrip("/")
    if not rel:
        return None
    target = (root / rel).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return None
    return target if target.is_file() else None


# ------------------------------------------------------------ png meta parse


def png_text_chunks(path, max_bytes=6_000_000):
    """Pull tEXt/zTXt/iTXt chunks out of a PNG. ComfyUI stashes the workflow here."""
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
                        chunks[key.decode("latin-1")] = zlib.decompress(
                            rest[1:]
                        ).decode("utf-8", "replace")
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
    """Reduce a ComfyUI API workflow to the handful of fields worth reading on a phone."""
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
                    info[key if key != "noise_seed" else "seed"] = ins[key]
            pos, neg = text_of(ins.get("positive")), text_of(ins.get("negative"))
            if pos:
                info["positive"] = pos
            if neg:
                info["negative"] = neg
        elif "CheckpointLoader" in cls and "ckpt_name" in ins:
            info["model"] = ins["ckpt_name"]
        elif "EmptyLatent" in cls:
            if not isinstance(ins.get("width"), list):
                info["width"] = ins.get("width")
            if not isinstance(ins.get("height"), list):
                info["height"] = ins.get("height")
    return info or None


def image_meta(path):
    if path.suffix.lower() != ".png":
        return None
    chunks = png_text_chunks(path)
    return summarize_workflow(chunks["prompt"]) if "prompt" in chunks else None


# ------------------------------------------------------------------- thumbs


def thumb_bytes(path, box=420):
    """Downscaled JPEG if Pillow is around, cached by path+mtime. None otherwise."""
    if not HAVE_PIL:
        return None
    try:
        st = path.stat()
        key = f"{abs(hash((str(path), st.st_mtime_ns)))}.jpg"
        cached = THUMB_DIR / key
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


# --------------------------------------------------------------- app icon


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


def make_icon(size=180):
    """Gold star on indigo - drawn by hand so the icon needs no image library."""
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


# ---------------------------------------------------------------- front end

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Renders</title>
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Renders">
<meta name="theme-color" content="#12102a">
<style>
:root{--bg:#12102a;--card:#1c1940;--ink:#ece9ff;--dim:#9d97c8;--gold:#e8b93a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)}
header{position:sticky;top:0;z-index:5;background:rgba(18,16,42,.94);
  backdrop-filter:blur(8px);padding:12px 14px 10px;border-bottom:1px solid #2b2757}
h1{margin:0 0 8px;font-size:17px;letter-spacing:.2px}
h1 span{color:var(--gold)}
#bar{display:flex;gap:8px;align-items:center}
input{flex:1;min-width:0;background:var(--card);border:1px solid #322d63;color:var(--ink);
  border-radius:9px;padding:9px 11px;font-size:16px}
button{background:var(--card);border:1px solid #322d63;color:var(--ink);
  border-radius:9px;padding:9px 12px;font-size:14px}
#count{color:var(--dim);font-size:12px;padding:6px 15px 0}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;padding:10px}
figure{margin:0;background:var(--card);border-radius:12px;overflow:hidden;position:relative}
figure img{display:block;width:100%;aspect-ratio:3/4;object-fit:cover;background:#221e4d}
figcaption{padding:6px 8px 8px;font-size:11px;color:var(--dim);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fresh::after{content:"new";position:absolute;top:7px;right:7px;background:var(--gold);
  color:#231c02;font-size:10px;font-weight:700;padding:2px 6px;border-radius:6px}
#empty{padding:40px 20px;text-align:center;color:var(--dim)}
#view{position:fixed;inset:0;background:rgba(8,7,20,.97);z-index:10;display:none;
  flex-direction:column;padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}
#view.on{display:flex}
#view img{flex:1;min-height:0;width:100%;object-fit:contain}
#meta{max-height:42vh;overflow:auto;padding:10px 14px 16px;font-size:12px;
  border-top:1px solid #2b2757}
#meta b{color:var(--gold);font-weight:600}
#meta .row{color:var(--dim);margin-bottom:6px}
#meta .p{color:var(--ink);white-space:pre-wrap;word-break:break-word}
#close{position:absolute;top:calc(env(safe-area-inset-top) + 8px);right:12px;z-index:11;
  background:rgba(28,25,64,.9)}
</style></head><body>
<header>
  <h1>ComfyUI <span>renders</span></h1>
  <div id="bar">
    <input id="q" placeholder="filter by filename" autocomplete="off">
    <button id="refresh">Refresh</button>
  </div>
</header>
<div id="count"></div>
<div id="grid"></div>
<div id="empty" hidden>No images yet. Render something.</div>
<div id="view"><button id="close">Close</button><img id="full" alt=""><div id="meta"></div></div>
<script>
const grid=document.getElementById('grid'), q=document.getElementById('q'),
      view=document.getElementById('view'), full=document.getElementById('full'),
      meta=document.getElementById('meta'), countEl=document.getElementById('count'),
      empty=document.getElementById('empty');
let items=[], seen=new Set(), first=true;

const ago=t=>{const s=(Date.now()/1000)-t;
  if(s<60)return'just now'; if(s<3600)return Math.floor(s/60)+'m ago';
  if(s<86400)return Math.floor(s/3600)+'h ago'; return Math.floor(s/86400)+'d ago';};

function draw(){
  const f=q.value.trim().toLowerCase();
  const show=items.filter(i=>!f||i.name.toLowerCase().includes(f));
  countEl.textContent=show.length+' image'+(show.length===1?'':'s');
  empty.hidden=show.length>0;
  grid.innerHTML='';
  for(const i of show){
    const fig=document.createElement('figure');
    if(i.fresh) fig.className='fresh';
    const img=document.createElement('img');
    img.loading='lazy'; img.src='/thumb/'+encodeURI(i.name); img.alt=i.name;
    img.onclick=()=>open(i);
    const cap=document.createElement('figcaption');
    cap.textContent=i.name.split('/').pop()+' · '+ago(i.mtime);
    fig.append(img,cap); grid.append(fig);
  }
}

async function open(i){
  full.src='/img/'+encodeURI(i.name);
  meta.innerHTML='<div class="row">'+i.name+'</div>';
  view.classList.add('on');
  try{
    const m=await (await fetch('/api/meta/'+encodeURI(i.name))).json();
    if(!m||!Object.keys(m).length){meta.innerHTML+='<div class="row">no workflow metadata</div>';return;}
    const bits=[];
    if(m.model)bits.push('<div class="row"><b>model</b> '+m.model+'</div>');
    const s=[]; for(const k of ['seed','steps','cfg','sampler_name','scheduler'])
      if(m[k]!==undefined)s.push(k+' '+m[k]);
    if(m.width&&m.height)s.unshift(m.width+'x'+m.height);
    if(s.length)bits.push('<div class="row">'+s.join(' · ')+'</div>');
    if(m.positive)bits.push('<div class="row"><b>prompt</b></div><div class="p">'+m.positive+'</div>');
    meta.innerHTML='<div class="row">'+i.name+'</div>'+bits.join('');
  }catch(e){}
}
document.getElementById('close').onclick=()=>{view.classList.remove('on');full.src='';};

async function load(){
  try{
    const fresh=await (await fetch('/api/list',{cache:'no-store'})).json();
    for(const i of fresh) i.fresh = !first && !seen.has(i.name);
    items=fresh; fresh.forEach(i=>seen.add(i.name)); first=false; draw();
  }catch(e){}
}
q.oninput=draw;
document.getElementById('refresh').onclick=load;
document.addEventListener('visibilitychange',()=>{if(!document.hidden)load();});
setInterval(load,8000);
load();
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "ComfyGallery/1.0"
    root = None

    def log_message(self, fmt, *args):
        pass  # quiet: this runs in a terminal the user is also using

    def _send(self, body, ctype, cache=None, code=200):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        path = posixpath.normpath(path)

        if path == "/":
            return self._send(PAGE, "text/html; charset=utf-8", "no-cache")

        if path == "/manifest.webmanifest":
            man = {
                "name": "ComfyUI renders",
                "short_name": "Renders",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#12102a",
                "theme_color": "#12102a",
                "icons": [
                    {"src": "/icon.png", "sizes": "180x180", "type": "image/png"},
                    {"src": "/icon.png", "sizes": "512x512", "type": "image/png"},
                ],
            }
            return self._send(json.dumps(man), "application/manifest+json", "max-age=3600")

        if path == "/icon.png":
            return self._send(make_icon(), "image/png", "max-age=86400")

        if path == "/api/list":
            return self._send(
                json.dumps(list_images(self.root)), "application/json", "no-store"
            )

        if path.startswith("/api/meta/"):
            target = safe_join(self.root, path[len("/api/meta/") :])
            if not target:
                return self._send("{}", "application/json", code=404)
            return self._send(
                json.dumps(image_meta(target) or {}), "application/json", "max-age=600"
            )

        if path.startswith("/img/") or path.startswith("/thumb/"):
            is_thumb = path.startswith("/thumb/")
            target = safe_join(self.root, path.split("/", 2)[2])
            if not target:
                return self._send("not found", "text/plain", code=404)
            if is_thumb:
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

        self._send("not found", "text/plain", code=404)


def lan_hints(port):
    """Best-effort list of URLs that will work from the phone."""
    urls = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127."):
                continue
            tag = "  (tailscale)" if ip.startswith("100.") else ""
            url = f"http://{ip}:{port}{tag}"
            if url not in urls:
                urls.append(url)
    except OSError:
        pass
    return urls


def main():
    ap = argparse.ArgumentParser(description="Phone gallery for ComfyUI renders")
    ap.add_argument("--dir", help="ComfyUI output folder (default: auto-detect)")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--host", default="0.0.0.0", help="default 0.0.0.0 so the phone can reach it")
    ap.add_argument("--log", help="append output here (autostart runs with no console)")
    args = ap.parse_args()

    if args.log:
        # pythonw.exe has no console, so without this a crash leaves no trace.
        stream = open(args.log, "a", buffering=1, encoding="utf-8", errors="replace")
        sys.stdout = sys.stderr = stream
        print(f"\n--- started {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    root = Path(args.dir).expanduser() if args.dir else detect_output_dir()
    if not root or not root.is_dir():
        print("Could not find ComfyUI's output folder.", file=sys.stderr)
        print("Pass it explicitly:  python server.py --dir <path>", file=sys.stderr)
        return 2

    Handler.root = root.resolve()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)

    n = len(list_images(Handler.root))
    print(f"Serving {n} image(s) from {Handler.root}")
    print(f"Thumbnails: {'Pillow' if HAVE_PIL else 'off (Pillow not installed)'}")
    for url in lan_hints(args.port) or [f"http://localhost:{args.port}"]:
        print(f"  {url}")
    print("\nOpen the tailscale URL on your phone, then Add to Home Screen. Ctrl-C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
