"""Capture tmux panes and summarize via an OpenAI-compatible chat API."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def capture_tmux_pane(tmux_name: str, scrollback_lines: int = 500) -> str:
    import shutil
    import subprocess

    tmux = shutil.which("tmux")
    if not tmux or not tmux_name.strip():
        return ""
    args = [tmux, "capture-pane", "-t", tmux_name.strip(), "-p"]
    if scrollback_lines > 0:
        args.extend(["-S", f"-{scrollback_lines}"])
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return "... [truncated]\n" + text[-max_chars:]


def build_capture_sections(captures: list[dict[str, Any]]) -> str:
    max_per = int(os.environ.get("SUMMARIZE_MAX_CHARS_PER_SESSION", "12000"))
    sections: list[str] = []
    for item in captures:
        title = item.get("title") or item.get("id") or "unknown"
        tmux_session = item.get("tmuxSession") or ""
        text = (item.get("text") or "").strip() or "(empty or tmux capture failed)"
        text = _truncate_text(text, max_per)
        sections.append(
            f"### Session: {title}\n"
            f"- id: {item.get('id', '')}\n"
            f"- tmux: {tmux_session}\n"
            f"```\n{text}\n```"
        )
    return "\n\n".join(sections)


def summarize_captures(captures: list[dict[str, Any]]) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set — export it to enable AI summarization"
        )

    if not captures:
        return "当前没有可汇总的 session。"

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip(
        "/"
    )
    model = os.environ.get("SUMMARIZE_MODEL", "gpt-4o-mini")
    timeout = int(os.environ.get("SUMMARIZE_TIMEOUT", "120"))

    system_prompt = (
        "You monitor multiple AI coding agents, each running in its own tmux terminal. "
        "The user will paste captured terminal scrollback from every session.\n\n"
        "Write the report in Chinese unless the terminals are clearly English-only.\n"
        "Structure:\n"
        "1. **总览** — one short paragraph on overall progress.\n"
        "2. **各 Session 状态** — for EACH session (use the session title from the input): "
        "status (running / waiting for user / stuck / done / error / idle), "
        "what it is doing, blockers if any, suggested next action.\n"
        "3. **需要优先关注** — ordered list of sessions that need human attention now.\n"
        "Be concise and actionable; do not invent facts not visible in the captures."
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": build_capture_sections(captures)},
        ],
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API error {exc.code}: {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM API unreachable: {exc.reason}") from exc

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("unexpected LLM API response shape") from exc
