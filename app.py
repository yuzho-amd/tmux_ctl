#!/usr/bin/env python3
"""Simple group-control server: spawn ttyd sessions and display them in a grid."""

from __future__ import annotations

import argparse
import atexit
import os
import secrets
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request

import db

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.jinja_env.auto_reload = True
AUTH_TOKEN = ""
db.init_db()


def _configure_auth(token: str) -> None:
    global AUTH_TOKEN
    AUTH_TOKEN = token.strip()
    app.config["AUTH_TOKEN"] = AUTH_TOKEN


def _request_token() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return (
        request.args.get("token", "").strip()
        or request.headers.get("X-Agent-Token", "").strip()
        or request.cookies.get("agent_ctl_token", "").strip()
    )


def _token_valid() -> bool:
    if not AUTH_TOKEN:
        return False
    supplied = _request_token()
    if not supplied:
        return False
    return secrets.compare_digest(supplied, AUTH_TOKEN)


def _unauthorized_response():
    if request.path.startswith("/api/"):
        return jsonify({"error": "unauthorized"}), 401
    if request.path != "/login":
        return redirect("/login")
    return render_template("login.html", error="")


@app.before_request
def _require_auth():
    if request.endpoint in ("login", "auth_cookie"):
        return None
    if _token_valid():
        return None
    return _unauthorized_response()


@app.after_request
def _disable_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

ROOT = os.path.dirname(os.path.abspath(__file__))
TTYD_DIR = os.path.join(ROOT, "ttyd")
TTYD_INDEX = os.path.join(TTYD_DIR, "index.html")
TTYD_SCROLLBAR_CSS = os.path.join(TTYD_DIR, "scrollbar.css")
TTYD_KEYHOOKS_JS = os.path.join(TTYD_DIR, "keyhooks.js")

BASE_PORT = int(os.environ.get("TTYD_BASE_PORT", "7681"))
TTYD_BIN = os.environ.get("TTYD_BIN", shutil.which("ttyd") or "")


@dataclass
class Session:
    id: str
    port: int
    process: subprocess.Popen[Any]
    title: str = field(default="")
    default_title: str = field(default="")
    tmux_session: str = field(default="")


sessions: dict[str, Session] = {}
_next_port = BASE_PORT


def _find_ttyd() -> str:
    if TTYD_BIN and os.path.isfile(TTYD_BIN) and os.access(TTYD_BIN, os.X_OK):
        return TTYD_BIN
    root = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.join(root, "bin", "ttyd"),
        "/usr/bin/ttyd",
        "/usr/local/bin/ttyd",
        shutil.which("ttyd") or "",
    ):
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ""


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def _allocate_port(preferred: int | None = None) -> int:
    global _next_port
    if preferred is not None and _port_free(preferred):
        _next_port = max(_next_port, preferred + 1)
        return preferred
    port = _next_port
    while not _port_free(port):
        port += 1
    _next_port = port + 1
    return port


def _tmux_session_name(session_id: str) -> str:
    return db.default_tmux_session(session_id)


def _shell_command(tmux_name: str) -> list[str]:
    if shutil.which("tmux"):
        return ["tmux", "new-session", "-A", "-s", tmux_name]
    return ["bash"]


def _tmux_has_session(name: str) -> bool:
    tmux = shutil.which("tmux")
    if not tmux:
        return False
    result = subprocess.run(
        [tmux, "has-session", "-t", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _list_system_tmux_sessions() -> list[dict[str, Any]]:
    tmux = shutil.which("tmux")
    if not tmux:
        return []
    result = subprocess.run(
        [
            tmux,
            "list-sessions",
            "-F",
            "#{session_name}\t#{session_windows}\t#{session_attached}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    items: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        name = parts[0]
        windows = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        attached = len(parts) > 2 and parts[2] == "1"
        items.append({"name": name, "windows": windows, "attached": attached})
    return items


def _kill_tmux_session_by_name(tmux_name: str) -> None:
    tmux = shutil.which("tmux")
    if not tmux:
        return
    subprocess.run(
        [tmux, "kill-session", "-t", tmux_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _kill_tmux_session(session_id: str, tmux_name: str | None = None) -> None:
    name = (tmux_name or _tmux_session_name(session_id)).strip()
    if db.count_sessions_with_tmux(name, exclude_id=session_id) > 0:
        return
    _kill_tmux_session_by_name(name)


def _spawn_ttyd(
    ttyd: str, port: int, index_html: str, tmux_name: str
) -> subprocess.Popen[Any]:
    return subprocess.Popen(
        [ttyd, "-p", str(port), "-W", "-I", index_html, *_shell_command(tmux_name)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _start_session(
    session_id: str,
    title: str,
    preferred_port: int | None = None,
    default_title: str | None = None,
    tmux_session: str | None = None,
) -> Session:
    ttyd = _find_ttyd()
    if not ttyd:
        raise RuntimeError("ttyd not found")

    default_title = (default_title or title).strip() or db.next_default_title()
    title = title.strip() or default_title
    tmux_name = (tmux_session or _tmux_session_name(session_id)).strip()

    port = _allocate_port(preferred_port)
    if preferred_port is not None and port != preferred_port:
        db.update_port(session_id, port)

    index_html = _ensure_ttyd_index(ttyd)
    proc = _spawn_ttyd(ttyd, port, index_html, tmux_name)
    session = Session(
        id=session_id,
        port=port,
        process=proc,
        title=title,
        default_title=default_title,
        tmux_session=tmux_name,
    )
    sessions[session_id] = session
    return session


def _row_to_titles(row: Any) -> tuple[str, str]:
    title = db.display_title(row)
    default_title = db.default_title_for(row)
    return title, default_title


def _ensure_sessions() -> None:
    global _next_port

    rows = db.list_sessions()
    max_port = BASE_PORT - 1
    for row in rows:
        max_port = max(max_port, int(row["port"]))
        existing = sessions.get(row["id"])
        title, default_title = _row_to_titles(row)
        if existing is not None and existing.process.poll() is None:
            existing.title = title
            existing.default_title = default_title
            existing.port = int(row["port"])
            existing.tmux_session = db.tmux_session_for(row)
            continue
        if existing is not None:
            sessions.pop(row["id"], None)
        try:
            tmux_name = db.tmux_session_for(row)
            _start_session(
                row["id"],
                title,
                int(row["port"]),
                default_title=default_title,
                tmux_session=tmux_name,
            )
        except Exception as exc:
            print(f"Warning: failed to restore session {row['id']}: {exc}")

    db_ids = {row["id"] for row in rows}
    for session_id in list(sessions.keys()):
        if session_id not in db_ids:
            _stop_session(sessions.pop(session_id))

    _next_port = max(_next_port, max_port + 1)


def _ordered_session_payloads() -> list[dict[str, Any]]:
    _ensure_sessions()
    payloads: list[dict[str, Any]] = []
    for row in db.list_sessions():
        session = sessions.get(row["id"])
        if session is not None:
            payloads.append(_session_payload(session))
    return payloads


def _get_session(session_id: str) -> Session | None:
    _ensure_sessions()
    session = sessions.get(session_id)
    if session is None:
        return None
    if session.process.poll() is not None:
        row = db.get_session(session_id)
        if row is None:
            sessions.pop(session_id, None)
            return None
        sessions.pop(session_id, None)
        try:
            title, default_title = _row_to_titles(row)
            tmux_name = db.tmux_session_for(row)
            return _start_session(
                row["id"],
                title,
                int(row["port"]),
                default_title=default_title,
                tmux_session=tmux_name,
            )
        except OSError:
            return None
    return session


def _client_host() -> str:
    host = request.host.split(":")[0]
    if host in ("0.0.0.0", ""):
        return "127.0.0.1"
    return host


def _session_url(port: int) -> str:
    return f"http://{_client_host()}:{port}"


def _session_payload(session: Session) -> dict[str, Any]:
    title = session.title.strip() or session.default_title.strip() or session.id
    default_title = session.default_title.strip() or title
    row = db.get_session(session.id)
    width, height = db.cell_size_for(row) if row is not None else (
        db.DEFAULT_CELL_WIDTH,
        db.DEFAULT_CELL_HEIGHT,
    )
    return {
        "id": session.id,
        "port": session.port,
        "url": _session_url(session.port),
        "title": title,
        "defaultTitle": default_title,
        "tmuxSession": session.tmux_session or _tmux_session_name(session.id),
        "width": width,
        "height": height,
    }


def _stop_proc(proc: subprocess.Popen[Any]) -> None:
    if proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=3)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass


def _stop_session(session: Session) -> None:
    _stop_proc(session.process)


def _scrollbar_css() -> str:
    with open(TTYD_SCROLLBAR_CSS, encoding="utf-8") as fh:
        return fh.read()


def _keyhooks_js() -> str:
    with open(TTYD_KEYHOOKS_JS, encoding="utf-8") as fh:
        return fh.read()


def _ttyd_patch_mtime() -> float:
    mtimes = []
    for path in (TTYD_SCROLLBAR_CSS, TTYD_KEYHOOKS_JS):
        if os.path.isfile(path):
            mtimes.append(os.path.getmtime(path))
    return max(mtimes) if mtimes else 0.0


def _fetch_default_ttyd_html(ttyd: str) -> str:
    port = BASE_PORT
    while not _port_free(port):
        port += 1
    proc = subprocess.Popen(
        [ttyd, "-p", str(port), "true"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        url = f"http://127.0.0.1:{port}/"
        for _ in range(50):
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                time.sleep(0.1)
        raise RuntimeError("timeout waiting for temp ttyd")
    finally:
        _stop_proc(proc)


def _ensure_ttyd_index(ttyd: str) -> str:
    os.makedirs(TTYD_DIR, exist_ok=True)
    patch_mtime = _ttyd_patch_mtime()
    if os.path.isfile(TTYD_INDEX) and os.path.getmtime(TTYD_INDEX) >= patch_mtime:
        return TTYD_INDEX

    html = _fetch_default_ttyd_html(ttyd)
    css_block = f"<style>\n{_scrollbar_css()}\n</style>"
    js_block = f"<script>\n{_keyhooks_js()}\n</script>"
    if "</head>" in html:
        html = html.replace("</head>", css_block + "\n</head>", 1)
    else:
        html = css_block + html
    if "</body>" in html:
        html = html.replace("</body>", js_block + "\n</body>", 1)
    else:
        html = html + js_block

    with open(TTYD_INDEX, "w", encoding="utf-8") as fh:
        fh.write(html)
    return TTYD_INDEX


def _cleanup_all() -> None:
    for session in list(sessions.values()):
        _stop_session(session)
    sessions.clear()


def _watch_files() -> list[str]:
    paths: list[str] = []
    templates_dir = os.path.join(ROOT, "templates")
    if os.path.isdir(templates_dir):
        for name in os.listdir(templates_dir):
            path = os.path.join(templates_dir, name)
            if os.path.isfile(path):
                paths.append(path)
    if os.path.isfile(TTYD_SCROLLBAR_CSS):
        paths.append(TTYD_SCROLLBAR_CSS)
    if os.path.isfile(TTYD_KEYHOOKS_JS):
        paths.append(TTYD_KEYHOOKS_JS)
    return paths


@app.route("/login", methods=["GET", "POST"])
def login():
    if _token_valid():
        return redirect("/")
    error = ""
    if request.method == "POST":
        token = (request.form.get("token") or "").strip()
        if token and secrets.compare_digest(token, AUTH_TOKEN):
            resp = redirect("/")
            resp.set_cookie(
                "agent_ctl_token",
                token,
                httponly=True,
                samesite="Lax",
                max_age=60 * 60 * 24 * 30,
            )
            return resp
        error = "Token 无效"
        return render_template("login.html", error=error), 401
    return render_template("login.html", error="")


@app.route("/auth")
def auth_cookie():
    token = request.args.get("token", "").strip()
    if not token or not secrets.compare_digest(token, AUTH_TOKEN):
        return render_template("login.html", error="Token 无效"), 401
    resp = redirect("/")
    resp.set_cookie(
        "agent_ctl_token",
        token,
        httponly=True,
        samesite="Lax",
        max_age=60 * 60 * 24 * 30,
    )
    return resp


@app.route("/")
def index():
    return render_template(
        "index.html",
        initial_sessions=_ordered_session_payloads(),
    )


@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    return jsonify(_ordered_session_payloads())


@app.route("/api/tmux/sessions", methods=["GET"])
def list_tmux_sessions():
    bound = db.bound_tmux_sessions()
    available: list[dict[str, Any]] = []
    for item in _list_system_tmux_sessions():
        if item["name"] in bound:
            continue
        available.append(item)
    return jsonify({"available": available})


@app.route("/api/sessions", methods=["POST"])
def create_session():
    _ensure_sessions()
    ttyd = _find_ttyd()
    if not ttyd:
        return jsonify({"error": "ttyd not found. Install ttyd and ensure it is on PATH."}), 503

    data = request.get_json(silent=True) or {}
    reuse_tmux = str(data.get("tmuxSession") or "").strip()

    session_id = uuid.uuid4().hex[:8]
    default_title = db.next_default_title()
    title = default_title

    if reuse_tmux:
        if reuse_tmux in db.bound_tmux_sessions():
            return jsonify({"error": f"tmux session already in use: {reuse_tmux}"}), 409
        if not _tmux_has_session(reuse_tmux):
            return jsonify({"error": f"tmux session not found: {reuse_tmux}"}), 404
        tmux_name = reuse_tmux
    else:
        tmux_name = _tmux_session_name(session_id)

    try:
        session = _start_session(
            session_id,
            title,
            default_title=default_title,
            tmux_session=tmux_name,
        )
    except OSError as exc:
        return jsonify({"error": f"failed to start ttyd: {exc}"}), 500

    db.save_session(
        session.id,
        session.title,
        session.port,
        session.default_title,
        tmux_session=session.tmux_session,
    )
    return jsonify(_session_payload(session)), 201


@app.route("/api/sessions/order", methods=["PUT"])
def reorder_sessions():
    data = request.get_json(silent=True) or {}
    order = data.get("order")
    if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
        return jsonify({"error": "order must be a list of session ids"}), 400

    known_ids = [row["id"] for row in db.list_sessions()]
    if set(order) != set(known_ids):
        return jsonify({"error": "order must include each session id exactly once"}), 400

    db.update_session_order(order)
    return jsonify({"ok": True})


@app.route("/api/sessions/reset-layout", methods=["POST"])
def reset_session_layout():
    _ensure_sessions()
    db.reset_all_cell_sizes()
    return jsonify(_ordered_session_payloads())


@app.route("/api/sessions/<session_id>", methods=["PATCH"])
def update_session(session_id: str):
    session = _get_session(session_id)
    if session is None:
        return jsonify({"error": "session not found"}), 404

    data = request.get_json(silent=True) or {}
    if "title" not in data and "width" not in data and "height" not in data:
        return jsonify({"error": "title, width, or height required"}), 400

    row = db.get_session(session_id)
    if row is None:
        return jsonify({"error": "session not found"}), 404

    if "title" in data:
        title = str(data["title"]).strip()
        default_title = db.default_title_for(row)
        title = title or default_title
        session.title = title
        session.default_title = default_title
        db.update_title(session_id, title)

    if "width" in data or "height" in data:
        width, height = db.cell_size_for(row)
        if "width" in data:
            width = int(data["width"])
        if "height" in data:
            height = int(data["height"])
        db.update_cell_size(session_id, width, height)

    return jsonify(_session_payload(session))


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id: str):
    _ensure_sessions()
    row = db.get_session(session_id)
    if row is None and session_id not in sessions:
        return jsonify({"error": "session not found"}), 404

    tmux_name = db.tmux_session_for(row) if row is not None else _tmux_session_name(session_id)
    session = sessions.pop(session_id, None)
    if session is not None:
        _stop_session(session)
    _kill_tmux_session(session_id, tmux_name)
    db.delete_session(session_id)
    return jsonify({"ok": True})


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent control terminal grid server")
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST", "0.0.0.0"),
        help="bind address (default: 0.0.0.0, env HOST)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "5000")),
        help="listen port (default: 5000, env PORT)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("AGENT_CTL_TOKEN", ""),
        help="access token (required; env AGENT_CTL_TOKEN)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=os.environ.get("DEBUG", "1").lower() in ("1", "true", "yes"),
        help="enable Flask debug mode",
    )
    parser.add_argument(
        "--no-debug",
        action="store_true",
        help="disable Flask debug mode",
    )
    args = parser.parse_args()
    if args.no_debug:
        args.debug = False
    if not (args.token or "").strip():
        parser.error("token is required — use --token or set AGENT_CTL_TOKEN")
    return args


if __name__ == "__main__":
    cli = _parse_args()
    _configure_auth(cli.token)
    host = cli.host
    port = cli.port
    debug = cli.debug
    print(f"Agent control UI: http://127.0.0.1:{port}/")
    print("Authentication: token required for all requests")
    if not _find_ttyd():
        print("Warning: ttyd not found — install ttyd before creating sessions.")
    else:
        if shutil.which("tmux"):
            print("Using tmux — terminal work area persists across refresh/restart.")
        else:
            print("Warning: tmux not found — install tmux to keep terminal state on refresh.")
        _ensure_sessions()
        if sessions:
            print(f"Restored {len(sessions)} session(s) from SQLite.")
    if debug:
        print("Debug mode: code changes will auto-reload the server.")
    else:
        atexit.register(_cleanup_all)
    app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=debug,
        extra_files=_watch_files() if debug else None,
    )
