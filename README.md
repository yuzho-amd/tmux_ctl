# TMUX CTL

[中文文档](README.cn.md)

A minimal multi-terminal web control panel.

![TMUX Ctl](images/image.jpg)

## Why TMUX Ctl?

Running one AI coding agent in a terminal is easy. Running ten of them is chaos.

The moment you start letting agents work in parallel — one fixing a bug, another writing tests, a third refactoring a module — you lose the ability to see what's happening. You end up juggling terminal tabs, SSH sessions, and tmux panes, constantly switching back and forth just to check "is it still working? is it stuck? did it finish?".

**TMUX Ctl gives you a single screen for all of them.** Every agent lives in its own live terminal cell, laid out as a grid in your browser. At a glance you can see which agents are making progress, which are waiting on you, and which need a nudge — without losing the full, interactive terminal for any of them.

- **See everything at once** — every running agent on one dashboard, no tab-hopping.
- **Stay in control** — each cell is a real, fully interactive terminal; jump in and type whenever you need to.
- **Nothing gets lost** — sessions live in tmux, so a refresh or restart never kills your work.
- **Reach it from anywhere** — it's just a web page, so you can monitor your agents from your laptop, tablet, or phone.

If you supervise multiple agents — or just want a tidy command center for several long-running terminals — this turns the mess into one calm, glanceable view.

## Requirements

- Python 3.10+
- [ttyd](https://github.com/tsl0922/ttyd)
- [tmux](https://github.com/tmux/tmux) (recommended — workspace survives refresh/restart)

## Install

```bash
# Ubuntu / Debian
sudo apt install ttyd tmux

# Or download ttyd into the project (no sudo)
bash setup_ttyd.sh

pip install -r requirements.txt
```

## Run

```bash
# Token is required (CLI flag or environment variable)
python app.py --token your-secret-token

# Custom port (default 5000)
python app.py --token your-secret-token -p 8080

# Or via environment variables
export AGENT_CTL_TOKEN=your-secret-token
python app.py -p 5000
```

Open http://127.0.0.1:5000 in your browser. On first visit you will see a login page — enter the **token** configured at startup.

One-shot login URL (sets cookie and redirects to home):

```
http://127.0.0.1:5000/auth?token=your-secret-token
```

## CLI flags

| Flag | Environment | Default | Description |
|------|-------------|---------|-------------|
| `--token` | `AGENT_CTL_TOKEN` | (required) | Access token; server refuses to start without it |
| `-p` / `--port` | `PORT` | `5000` | Listen port |
| `--host` | `HOST` | `0.0.0.0` | Bind address |
| `--debug` | `DEBUG=1` | on | Debug / auto-reload |
| `--no-debug` | — | — | Disable debug mode |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_CTL_TOKEN` | (required) | Access token; can also pass `--token` |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `5000` | Listen port |
| `DEBUG` | `1` | Debug mode (auto-reload on code changes) |
| `TTYD_BASE_PORT` | `7681` | First ttyd port |
| `TTYD_BIN` | auto-detect | Path to ttyd binary |

## Authentication

| Method | Description |
|--------|-------------|
| Login page | Visit `/` → redirect to `/login`; valid token is stored in an HttpOnly cookie |
| URL | `GET /auth?token=...` validates and sets cookie |
| Headers | `Authorization: Bearer <token>` or `X-Agent-Token: <token>` |

## Usage

1. Click **+** (bottom-right) to create a session
2. Click a title to edit the label
3. Drag **⠿** to reorder cells; drag the **bottom-right corner** to resize
4. Click **⤢** to maximize; **Esc** or **Minimize** returns to the grid
5. **Reset windows** (header) restores all cells to the default size
6. Click **×** on a cell to close the session
