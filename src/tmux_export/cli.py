"""tmux-export: capture and export tmux pane content as txt/tty/html."""

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ansi2html import Ansi2HTMLConverter

CACHE_DIR = Path.home() / ".cache" / "tmux-export"


# ---------------------------------------------------------------------------
# Remote / local command execution
# ---------------------------------------------------------------------------

def run_cmd(host, cmd, *, check=True):
    if host:
        remote = " ".join(shlex.quote(c) for c in cmd)
        full = ["ssh", host, remote]
    else:
        full = cmd
    return subprocess.run(full, capture_output=True, text=True, check=check)


def run_cmd_bytes(host, cmd):
    if host:
        remote = " ".join(shlex.quote(c) for c in cmd)
        full = ["ssh", host, remote]
    else:
        full = cmd
    r = subprocess.run(full, capture_output=True, check=True)
    return r.stdout


# ---------------------------------------------------------------------------
# tmux helpers
# ---------------------------------------------------------------------------

def list_sessions(host):
    fmt = "#{session_name}\t#{session_windows}\t#{?session_attached,attached,detached}"
    r = run_cmd(host, ["tmux", "list-sessions", "-F", fmt], check=False)
    if r.returncode != 0:
        return []
    out = []
    for line in r.stdout.strip().splitlines():
        name, wins, status = line.split("\t")
        out.append({"name": name, "windows": int(wins), "status": status})
    return out


def list_windows(host, session):
    fmt = "#{window_index}\t#{window_name}\t#{window_panes}"
    r = run_cmd(host, ["tmux", "list-windows", "-t", session, "-F", fmt])
    out = []
    for line in r.stdout.strip().splitlines():
        idx, name, panes = line.split("\t")
        out.append({"index": int(idx), "name": name, "panes": int(panes)})
    return out


def list_panes(host, session, window):
    target = f"{session}:{window}"
    fmt = "#{pane_index}\t#{pane_current_command}\t#{pane_width}\t#{pane_height}\t#{pane_current_path}"
    r = run_cmd(host, ["tmux", "list-panes", "-t", target, "-F", fmt])
    out = []
    for line in r.stdout.strip().splitlines():
        idx, cmd_, w, h, path = line.split("\t")
        out.append({
            "index": int(idx), "command": cmd_,
            "width": int(w), "height": int(h), "path": path,
        })
    return out


def capture_pane(host, session, window, pane, *, escape_codes=False, scrollback=None):
    target = f"{session}:{window}.{pane}"
    cmd = ["tmux", "capture-pane", "-p", "-J"]
    if escape_codes:
        cmd.append("-e")
    if scrollback is not None:
        cmd.extend(["-S", str(-scrollback)])
    else:
        cmd.extend(["-S", "-"])
    cmd.extend(["-t", target])
    return run_cmd_bytes(host, cmd)


# ---------------------------------------------------------------------------
# Interactive picker
# ---------------------------------------------------------------------------

def pick(items, prompt):
    print(f"\n{prompt}")
    for i, item in enumerate(items):
        print(f"  {i}: {item}")
    while True:
        try:
            raw = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(1)
        if raw.isdigit() and 0 <= int(raw) < len(items):
            return int(raw)
        print(f"  enter 0-{len(items)-1}")


def interactive_pick(host):
    sessions = list_sessions(host)
    if not sessions:
        target = host or "localhost"
        print(f"error: no tmux sessions on {target}", file=sys.stderr)
        sys.exit(1)

    if len(sessions) == 1:
        si = 0
        print(f"\nonly one session: {sessions[0]['name']}")
    else:
        labels = [f"{s['name']}  ({s['windows']} windows, {s['status']})" for s in sessions]
        si = pick(labels, "pick a session:")
    session = sessions[si]["name"]

    windows = list_windows(host, session)
    if len(windows) == 1:
        wi = 0
    else:
        labels = [f"{w['index']}: {w['name']}  ({w['panes']} panes)" for w in windows]
        wi = pick(labels, "pick a window:")
    window = windows[wi]["index"]

    panes = list_panes(host, session, window)
    if len(panes) == 1:
        pi = 0
    else:
        labels = [f"{p['index']}: {p['command']}  [{p['width']}x{p['height']}]" for p in panes]
        pi = pick(labels, "pick a pane:")
    pane = panes[pi]["index"]

    host_arg = host or ""
    if host_arg:
        host_arg += " "
    direct = f"tmux-export {host_arg}-s {shlex.quote(session)} -w {window} -p {pane}"
    print(f"\nnext time, run:\n  {direct}\n")

    return session, window, pane


# ---------------------------------------------------------------------------
# TOML writer (no external deps)
# ---------------------------------------------------------------------------

def _toml_val(v):
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    return f'"{v}"'


def write_toml(path, data):
    lines = []
    for section, kvs in data.items():
        lines.append(f"[{section}]")
        for k, v in kvs.items():
            if v is not None:
                lines.append(f"{k} = {_toml_val(v)}")
        lines.append("")
    path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# HTML conversion
# ---------------------------------------------------------------------------

_converter = None

TERMINAL_CSS = """\
html, body {
  margin: 0; padding: 0;
  background: #1a1a1a;
  color: #d4d4d4;
}
.terminal-wrap {
  font-family: 'JetBrains Mono', 'SF Mono', 'Menlo', 'Consolas', 'Liberation Mono', monospace;
  font-size: 13px;
  line-height: 1.18;
  padding: 16px;
  overflow-x: auto;
}
.terminal-wrap .ansi2html-content {
  white-space: pre;
}
.terminal-header {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 11px;
  color: #888;
  padding: 8px 16px;
  border-bottom: 1px solid #333;
  background: #141414;
}
"""


def tty_to_html(tty_bytes, title="tmux-export"):
    global _converter
    if _converter is None:
        _converter = Ansi2HTMLConverter(dark_bg=True, scheme="xterm")
    text = tty_bytes.decode("utf-8", errors="replace")
    body = _converter.convert(text, full=False)
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
{TERMINAL_CSS}
{_converter.produce_headers().replace('<style type="text/css">', '').replace('</style>', '')}
</style>
</head>
<body>
<div class="terminal-header">{title}</div>
<div class="terminal-wrap">
<pre class="ansi2html-content">{body}</pre>
</div>
</body>
</html>"""
    return html.encode("utf-8")


# ---------------------------------------------------------------------------
# Capture & save
# ---------------------------------------------------------------------------

def do_capture(host, session, window, pane, formats, scrollback, output_dir):
    panes = list_panes(host, session, window)
    pane_info = next((p for p in panes if p["index"] == pane), None)

    hostname = "local"
    user = ""
    if host:
        if "@" in host:
            user, hostname = host.split("@", 1)
        else:
            hostname = host

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d-%H%M%S")

    if output_dir:
        out = output_dir
    else:
        out = CACHE_DIR / hostname / session / f"w{window}p{pane}"
    out.mkdir(parents=True, exist_ok=True)

    written = {}

    # txt
    if "txt" in formats or "all" in formats:
        txt = capture_pane(host, session, window, pane, escape_codes=False, scrollback=scrollback)
        p = out / f"{ts}.txt"
        p.write_bytes(txt)
        written["txt"] = p
        print(f"  txt -> {p}")

    # tty
    tty = None
    if "tty" in formats or "html" in formats or "all" in formats:
        tty = capture_pane(host, session, window, pane, escape_codes=True, scrollback=scrollback)
        if "tty" in formats or "all" in formats:
            p = out / f"{ts}.tty"
            p.write_bytes(tty)
            written["tty"] = p
            print(f"  tty -> {p}")

    # html
    if ("html" in formats or "all" in formats) and tty is not None:
        title = f"{hostname}:{session}:{window}.{pane}"
        html = tty_to_html(tty, title=title)
        p = out / f"{ts}.html"
        p.write_bytes(html)
        written["html"] = p
        print(f"  html -> {p}")

    # metadata
    meta = {
        "capture": {
            "hostname": hostname,
            "user": user,
            "session": session,
            "window": window,
            "pane": pane,
            "timestamp": now.isoformat(),
            "pane_width": pane_info["width"] if pane_info else 0,
            "pane_height": pane_info["height"] if pane_info else 0,
            "pane_command": pane_info["command"] if pane_info else "",
            "pane_path": pane_info["path"] if pane_info else "",
        },
        "files": {k: f"{ts}.{k}" for k in written},
    }
    toml_path = out / f"{ts}.toml"
    write_toml(toml_path, meta)
    print(f"  meta -> {toml_path}")

    return out, ts, written


# ---------------------------------------------------------------------------
# Load utility
# ---------------------------------------------------------------------------

def do_load(path_str):
    path = Path(path_str).resolve()
    if not path.exists():
        print(f"error: {path} not found", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("TMUX"):
        print("error: not inside a tmux session. run this from within tmux.", file=sys.stderr)
        sys.exit(1)

    name = f"export:{path.stem}"
    subprocess.run(["tmux", "new-window", "-n", name], check=True)
    if path.suffix == ".tty":
        cmd = f"cat {shlex.quote(str(path))}"
    else:
        cmd = f"less {shlex.quote(str(path))}"
    subprocess.run(["tmux", "send-keys", "-t", f":{name}", cmd, "Enter"], check=True)
    print(f"opened in tmux window '{name}'")


# ---------------------------------------------------------------------------
# Host (gist) utility
# ---------------------------------------------------------------------------

def do_host(path_str, host, session, window, pane, formats, scrollback):
    if not shutil.which("gh"):
        print("error: gh CLI not installed (brew install gh)", file=sys.stderr)
        sys.exit(1)

    html_path = None

    if path_str:
        p = Path(path_str).resolve()
        if p.suffix == ".html" and p.exists():
            html_path = p
        elif p.suffix == ".tty" and p.exists():
            html_bytes = tty_to_html(p.read_bytes())
            html_path = p.with_suffix(".html")
            html_path.write_bytes(html_bytes)
            print(f"  converted {p.name} -> {html_path.name}")
        elif p.exists():
            print(f"error: {p.suffix} files can't be hosted. use .html or .tty", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"error: {p} not found", file=sys.stderr)
            sys.exit(1)
    else:
        if session is None:
            session, window, pane = interactive_pick(host)
        if window is None:
            window = 0

        print(f"capturing {host or 'local'}:{session}:{window}.{pane}")
        out, ts, written = do_capture(host, session, window, pane, formats, scrollback, None)

        if "html" in written:
            html_path = written["html"]
        else:
            tty = capture_pane(host, session, window, pane, escape_codes=True, scrollback=scrollback)
            html_path = out / f"{ts}.html"
            html_path.write_bytes(tty_to_html(tty))

    gist_name = html_path.name

    r = subprocess.run(
        ["gh", "gist", "create", "--public", str(html_path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"error creating gist: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    gist_url = r.stdout.strip()
    gist_id = gist_url.rstrip("/").rsplit("/", 1)[-1]

    print(f"\n  gist:    {gist_url}")
    print(f"  preview: https://gistpreview.github.io/?{gist_id}/{gist_name}")


# ---------------------------------------------------------------------------
# URI parsing
# ---------------------------------------------------------------------------

def parse_uri(uri):
    m = re.match(r'^([^:]+):/tmux/([^/]+)/(\d+)/(\d+)$', uri)
    if not m:
        raise ValueError(f"invalid URI: {uri}")
    return m.group(1), m.group(2), int(m.group(3)), int(m.group(4))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        prog="tmux-export",
        description="Capture and export tmux pane content.",
    )
    p.add_argument("target", nargs="?", default=None,
                   help="[user@]host, or URI like host:/tmux/session/window/pane")
    p.add_argument("-s", "--session", default=None, help="tmux session name")
    p.add_argument("-w", "--window", type=int, default=None, help="window index")
    p.add_argument("-p", "--pane", type=int, default=0, help="pane index (default 0)")
    p.add_argument("-f", "--format", default="all",
                   help="comma-separated: txt,tty,html,all (default: all)")
    p.add_argument("--scrollback", type=int, default=None,
                   help="lines of scrollback (default: all)")
    p.add_argument("--output", default=None, help="output directory override")
    p.add_argument("--load", metavar="PATH", default=None,
                   help="load a .txt or .tty export into a tmux window")
    p.add_argument("--host", nargs="?", const="__capture__", default=None, metavar="PATH",
                   help="upload HTML to GitHub Gist (requires gh CLI)")

    args = p.parse_args()

    if args.load:
        do_load(args.load)
        return

    if args.host is not None:
        host_path = None if args.host == "__capture__" else args.host
        host = None
        session = args.session
        window = args.window
        pane = args.pane
        if args.target:
            if ":/tmux/" in args.target:
                host, session, window, pane = parse_uri(args.target)
            else:
                host = args.target
        formats = set(args.format.split(","))
        do_host(host_path, host, session, window, pane, formats, args.scrollback)
        return

    host = None
    session = args.session
    window = args.window
    pane = args.pane

    if args.target:
        if ":/tmux/" in args.target:
            host, session, window, pane = parse_uri(args.target)
        else:
            host = args.target

    if session is None:
        session, window, pane = interactive_pick(host)

    if window is None:
        window = 0

    formats = set(args.format.split(","))
    output_dir = Path(args.output) if args.output else None

    print(f"capturing {host or 'local'}:{session}:{window}.{pane}")
    do_capture(host, session, window, pane, formats, args.scrollback, output_dir)


if __name__ == "__main__":
    main()
