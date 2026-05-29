# Agent Control

[中文文档](README.cn.md)

A minimal multi-terminal control panel: Flask serves the web UI; each session is rendered as a grid cell via [ttyd](https://github.com/tsl0922/ttyd); [tmux](https://github.com/tmux/tmux) persists the underlying terminal workspace.

## Architecture

```
Browser cell (iframe)
    ↓ HTTP / WebSocket
  ttyd (one port per session)
    ↓
  tmux session (agent-{id})
    ↓
  bash / your workloads
```

- **Flask**: Web UI, API, session management
- **SQLite** (`data/sessions.db`): Session metadata (id, title, port, sort order, window size, tmux binding)
- **ttyd**: Exposes terminals to the browser
- **tmux**: Holds real terminal state (cwd, processes, scrollback)

## Requirements

- Python 3.10+
- [ttyd](https://github.com/tsl0922/ttyd) (web terminal)
- [tmux](https://github.com/tmux/tmux) (**recommended** — workspace survives refresh/restart)

### Install

```bash
# Ubuntu / Debian
sudo apt install ttyd tmux

# Or download ttyd into the project (no sudo)
bash setup_ttyd.sh
```

## Run

```bash
pip install -r requirements.txt

# Token is required (CLI or environment variable)
python app.py --token your-secret-token

# Custom port (default 5000)
python app.py --token your-secret-token -p 8080

# Or use environment variables
export AGENT_CTL_TOKEN=your-secret-token
python app.py -p 5000
```

Open http://127.0.0.1:5000 in your browser. On first visit you will see a login page — enter the **token** configured at startup.

One-shot login URL (sets cookie and redirects to home):

```
http://127.0.0.1:5000/auth?token=your-secret-token
```

### CLI flags

| Flag | Environment | Default | Description |
|------|-------------|---------|-------------|
| `--token` | `AGENT_CTL_TOKEN` | (required) | Access token; server refuses to start without it |
| `-p` / `--port` | `PORT` | `5000` | Flask listen port |
| `--host` | `HOST` | `0.0.0.0` | Bind address |
| `--debug` | `DEBUG=1` | on | Flask debug / auto-reload |
| `--no-debug` | — | — | Disable debug mode |

## Authentication

A token **must** be set at startup. All web pages and `/api/*` endpoints are protected; unauthorized requests are rejected.

| Method | Description |
|--------|-------------|
| Login page | Visit `/` → redirect to `/login`; valid token is stored in an HttpOnly cookie |
| URL | `GET /auth?token=...` validates and sets cookie |
| Headers | `Authorization: Bearer <token>` or `X-Agent-Token: <token>` |
| API | Missing/invalid token → `401` |

> Note: ttyd terminal iframes connect directly to their own ports (7681+), not through Flask auth. The control UI and API are token-protected.

## Usage

1. Click **+** (bottom-right) to create a session (optionally reuse an existing tmux session or create a new one)
2. Click a title to edit the label (saved in SQLite)
3. Drag **⠿** to reorder cells; drag the **bottom-right corner** to resize (flex flow layout)
4. Click **⤢** to maximize; **Esc** or **Minimize** returns to the grid; after minimize, click **Repaint** on the terminal overlay to keep editing in the small window
5. **Reset windows** (header) restores all cells to the default size (320×240)
6. Click **×** on a cell to close the session (also kills the tmux session unless another cell reuses it)

## How tmux integration works

When a session is created, the backend runs:

```bash
ttyd -p <port> -W -I ttyd/index.html \
  tmux new-session -A -s agent-<session_id>
```

| Piece | Role |
|-------|------|
| `tmux new-session -A -s agent-xxx` | **Attach** if the tmux session exists, otherwise **create** |
| `agent-<session_id>` | Matches the SQLite session id for recovery |
| ttyd | Web display only; can be restarted and re-attach to the same tmux |

Behavior:

- **Browser refresh**: iframe reconnects to ttyd → same tmux → workspace preserved
- **Flask restart**: sessions restored from SQLite, ttyd respawned, tmux re-attached → workspace preserved
- **Close session (×)**: stops ttyd and runs `tmux kill-session -t agent-xxx` → full cleanup

Without tmux, the command falls back to plain `bash`; terminal state is **not** preserved across refresh/restart.

### Inspect tmux manually

```bash
tmux ls                  # list agent-* sessions
tmux attach -t agent-xxx # attach the same session locally
```

## Persistence

| Data | Page refresh | Server restart | Close session |
|------|--------------|----------------|---------------|
| Grid / titles | ✅ SQLite | ✅ SQLite | ❌ deleted |
| Terminal workspace (tmux) | ✅ | ✅ | ❌ tmux killed |
| ttyd process | reconnect | auto respawn | stopped |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_CTL_TOKEN` | (required) | Access token; can also pass `--token` |
| `HOST` | `0.0.0.0` | Flask bind address |
| `PORT` | `5000` | Flask port |
| `DEBUG` | `1` | Debug mode (auto-reload on code changes) |
| `TTYD_BASE_PORT` | `7681` | First ttyd port |
| `TTYD_BIN` | auto-detect | Path to ttyd binary |

## API overview

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/sessions` | List sessions |
| `POST` | `/api/sessions` | Create (optional `{ "tmuxSession": "..." }` to reuse tmux) |
| `PATCH` | `/api/sessions/<id>` | Update title or size `{ "width", "height" }` |
| `DELETE` | `/api/sessions/<id>` | Delete session |
| `PUT` | `/api/sessions/order` | Reorder `{ "order": ["id", ...] }` |
| `POST` | `/api/sessions/reset-layout` | Reset all cells to default size |
| `GET` | `/api/tmux/sessions` | List tmux sessions available for reuse |
