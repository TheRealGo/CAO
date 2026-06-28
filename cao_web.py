#!/usr/bin/env python3
"""Local read-only CAO dashboard.

The dashboard intentionally reads tmux state directly instead of asking workers
to write status files. It is local-only by default and exposes no send controls.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_LINES = 100
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
CODEX_SESSIONS_DIR = Path.home() / ".codex" / "sessions"
CODEX_SESSION_SCAN_TTL = 15.0
CODEX_SESSION_SCAN_LIMIT = 120
TRANSCRIPT_REVERSE_READ_LINES = 6000
_CODEX_SESSION_CACHE: dict[str, tuple[float, Path | None]] = {}


WORKING_RE = re.compile(
    r"Working \(|background terminal running|shell still running|Running |Calling ",
    re.I,
)
BLOCKED_RE = re.compile(
    r"usage limit|Conversation interrupted|Reviewing approval request|requires approval|"
    r"blocked|Goal blocked",
    re.I,
)
READY_RE = re.compile(r"Ready|❯|›|new task\?", re.I)
NEEDS_USER_RE = re.compile(
    r"ユーザー判断|判断待ち|承認待ち|ご判断|ご指示|どれを進めますか|"
    r"requires approval|approve this|please approve|required next action|next user",
    re.I,
)


@dataclass
class AgentCard:
    id: str
    session: str
    window: str
    pane_id: str
    runner: str
    state: str
    needs_user: bool
    cwd: str
    command: str
    updated_at: float
    last_response: str
    last_response_source: str


def run_tmux(args: list[str], *, check: bool = False) -> str:
    proc = subprocess.run(
        ["tmux", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=check,
    )
    return proc.stdout


def tmux_available() -> bool:
    try:
        subprocess.run(
            ["tmux", "-V"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except Exception:
        return False
    return True


def capture_pane(pane_id: str, lines: int = DEFAULT_LINES) -> str:
    return run_tmux(["capture-pane", "-J", "-p", "-t", pane_id, "-S", f"-{lines}"])


def infer_state(text: str, pane_exists: bool = True) -> str:
    if not pane_exists:
        return "missing"
    tail = "\n".join(nonempty_lines(text, drop_prompt_placeholder=False)[-35:])
    if WORKING_RE.search(tail):
        return "working"
    if READY_RE.search(tail):
        return "ready"
    if BLOCKED_RE.search(tail):
        return "blocked"
    return "idle"


def nonempty_lines(text: str, *, drop_prompt_placeholder: bool = True) -> list[str]:
    physical_lines: list[tuple[str, bool]] = []
    after_blank = False
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            after_blank = True
            continue
        if set(stripped) <= {"─", "━", "═", "╴", " "}:
            after_blank = True
            continue
        if stripped.startswith(("~/", "[", "⏵⏵ auto mode")):
            continue
        if drop_prompt_placeholder and re.match(r"^› .+@filename$", stripped):
            continue
        physical_lines.append((line, after_blank))
        after_blank = False
    return join_wrapped_lines(physical_lines)


def join_wrapped_lines(lines: list[tuple[str, bool]]) -> list[str]:
    logical: list[str] = []
    for line, after_blank in lines:
        stripped = line.strip()
        if logical and not after_blank and is_wrapped_continuation(line):
            logical[-1] = f"{logical[-1].rstrip()}{wrap_separator(logical[-1], stripped)}{stripped}"
            continue
        logical.append(line)
    return logical


def is_wrapped_continuation(line: str) -> bool:
    if not line.startswith("  "):
        return False
    stripped = line.strip()
    if stripped.startswith(
        (
            "│",
            "├",
            "└",
            "┌",
            "┬",
            "┤",
            "•",
            "-",
            "✔",
            "⚠",
            "✻",
            "❯",
            "›",
            "□",
        )
    ):
        return False
    if re.match(r"^\d+\.", stripped):
        return False
    return True


def wrap_separator(previous: str, current: str) -> str:
    left = previous.rstrip()[-1:]
    right = current[:1]
    if not left or not right:
        return ""
    if is_cjk(left):
        return ""
    if is_ascii_alnum(left) and is_ascii_alnum(right):
        return " "
    if left in "/([{<「『（、。" or right in ".,;:!?)]}>、。）」』":
        return ""
    return " "


def is_cjk(char: str) -> bool:
    return bool(re.match(r"[\u3040-\u30ff\u3400-\u9fff]", char))


def is_ascii_alnum(char: str) -> bool:
    return char.isascii() and char.isalnum()


def tail_excerpt(text: str, limit: int = 12) -> list[str]:
    lines = nonempty_lines(text)
    return lines[-limit:]


def first_matching_tail(text: str, pattern: re.Pattern[str], limit: int = 80) -> str:
    lines = nonempty_lines(text)[-limit:]
    for line in reversed(lines):
        if pattern.search(line):
            return line.strip()
    return ""


def next_line(text: str) -> str:
    patterns = [
        re.compile(r"(Working \(|Calling |Running |ここで停止|次|Next|next|Required next action|再開に必要|完了条件)", re.I),
        re.compile(r"(Phase|Plan|TODO|pending|blocked)", re.I),
    ]
    for pattern in patterns:
        line = first_matching_tail(text, pattern)
        if line:
            return line
    lines = nonempty_lines(text)
    return lines[-1].strip() if lines else ""


def decision_line(text: str) -> str:
    stopping_line = first_matching_tail(text, re.compile(r"ここで停止|特に.+ご判断", re.I))
    if stopping_line:
        return stopping_line
    return first_matching_tail(text, NEEDS_USER_RE)


def text_from_content(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in {"text", "output_text", "input_text"} and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(part for part in parts if part).strip()


def recent_lines_reverse(path: Path, max_lines: int = TRANSCRIPT_REVERSE_READ_LINES) -> Iterable[str]:
    try:
        with path.open("rb") as file:
            file.seek(0, os.SEEK_END)
            position = file.tell()
            pending = b""
            yielded = 0
            while position > 0 and yielded < max_lines:
                read_size = min(65536, position)
                position -= read_size
                file.seek(position)
                chunk = file.read(read_size)
                parts = (chunk + pending).splitlines()
                if position > 0 and parts:
                    pending = parts[0]
                    parts = parts[1:]
                else:
                    pending = b""
                for raw in reversed(parts):
                    if yielded >= max_lines:
                        return
                    yielded += 1
                    yield raw.decode("utf-8", errors="replace")
            if pending and yielded < max_lines:
                yield pending.decode("utf-8", errors="replace")
    except OSError:
        return


def extract_claude_assistant_text(path: Path) -> str:
    for line in recent_lines_reverse(path):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("isSidechain"):
            continue
        message = record.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        text = text_from_content(message.get("content"))
        if text:
            return text
    return ""


def claude_project_slug(cwd: str) -> str:
    return str(Path(cwd)).replace("/", "-")


def latest_claude_project_log(cwd: str) -> Path | None:
    project_dir = CLAUDE_PROJECTS_DIR / claude_project_slug(cwd)
    if not project_dir.is_dir():
        return None
    logs = list(project_dir.glob("*.jsonl"))
    if not logs:
        return None
    return max(logs, key=lambda path: path.stat().st_mtime)


def recent_codex_session_files(limit: int = CODEX_SESSION_SCAN_LIMIT) -> list[Path]:
    if not CODEX_SESSIONS_DIR.is_dir():
        return []
    files: list[Path] = []
    for root, _, names in os.walk(CODEX_SESSIONS_DIR):
        for name in names:
            if name.endswith(".jsonl"):
                files.append(Path(root) / name)
    files.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0.0, reverse=True)
    return files[:limit]


def codex_session_cwd(path: Path) -> str:
    try:
        with path.open(encoding="utf-8") as file:
            for index, line in enumerate(file):
                if index > 40:
                    break
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = record.get("payload")
                if isinstance(payload, dict) and isinstance(payload.get("cwd"), str):
                    return payload["cwd"]
    except OSError:
        return ""
    return ""


def latest_codex_session_log(cwd: str) -> Path | None:
    now = time.time()
    cached = _CODEX_SESSION_CACHE.get(cwd)
    if cached and now - cached[0] < CODEX_SESSION_SCAN_TTL:
        return cached[1] if cached[1] and cached[1].exists() else None

    best: Path | None = None
    for path in recent_codex_session_files():
        if codex_session_cwd(path) != cwd:
            continue
        best = path
        break
    _CODEX_SESSION_CACHE[cwd] = (now, best)
    return best


def extract_codex_assistant_text(path: Path) -> str:
    for line in recent_lines_reverse(path):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") == "task_complete" and isinstance(payload.get("last_agent_message"), str):
            return payload["last_agent_message"].strip()
        if payload.get("type") == "message" and payload.get("role") == "assistant":
            text = text_from_content(payload.get("content"))
            if text:
                return text
    return ""


def latest_transcript_response(runner: str, cwd: str) -> tuple[str, str]:
    normalized_runner = runner.lower()
    if normalized_runner == "claude":
        path = latest_claude_project_log(cwd)
        if not path:
            return "", ""
        return extract_claude_assistant_text(path), f"Claude transcript: {path.name}"
    if normalized_runner == "codex":
        path = latest_codex_session_log(cwd)
        if not path:
            return "", ""
        return extract_codex_assistant_text(path), f"Codex transcript: {path.name}"
    return "", ""


def manager_window_id(session: str) -> str:
    configured = run_tmux(["show-options", "-qv", "-t", session, "@cao_manager_window"]).strip()
    if configured:
        return configured
    if os.environ.get("TMUX"):
        current = run_tmux(["display-message", "-p", "#{session_name}|#{window_id}"]).strip()
        if "|" in current:
            current_session, window_id = current.split("|", 1)
            if current_session == session:
                return window_id
    return ""


def list_panes() -> list[dict[str, str]]:
    fmt = "#{session_name}\t#{window_name}\t#{window_id}\t#{pane_id}\t#{pane_current_path}\t#{pane_current_command}\t#{@cao_runner}\t#{pane_active}"
    rows = run_tmux(["list-panes", "-a", "-F", fmt]).splitlines()
    panes: list[dict[str, str]] = []
    for row in rows:
        parts = row.split("\t")
        if len(parts) < 8:
            continue
        session, window, window_id, pane_id, cwd, command, runner, pane_active = parts[:8]
        if pane_active != "1":
            continue
        panes.append(
            {
                "session": session,
                "window": window,
                "window_id": window_id,
                "pane_id": pane_id,
                "cwd": cwd,
                "command": command,
                "runner": runner or "?",
            }
        )
    return panes


def collect_cards(lines: int = DEFAULT_LINES) -> list[AgentCard]:
    if not tmux_available():
        return []

    current_session = os.environ.get("CAO_SESSION", "CAO")
    manager = manager_window_id(current_session)
    cards: list[AgentCard] = []
    seen: set[str] = set()
    for pane in list_panes():
        if pane["pane_id"] in seen:
            continue
        seen.add(pane["pane_id"])
        if pane["session"] == current_session and pane["window_id"] == manager:
            continue
        text = capture_pane(pane["pane_id"], lines=lines)
        state = infer_state(text)
        decision = decision_line(text)
        needs_user = state == "blocked" or (state == "ready" and bool(decision))
        last_response, last_response_source = latest_transcript_response(pane["runner"], pane["cwd"])
        if not last_response:
            last_response = "\n".join(tail_excerpt(text))
            last_response_source = "tmux visible tail fallback"
        cards.append(
            AgentCard(
                id=pane["pane_id"],
                session=pane["session"],
                window=pane["window"],
                pane_id=pane["pane_id"],
                runner=pane["runner"],
                state=state,
                needs_user=needs_user,
                cwd=pane["cwd"],
                command=pane["command"],
                updated_at=time.time(),
                last_response=last_response,
                last_response_source=last_response_source,
            )
        )
    return sorted(cards, key=lambda c: (not c.needs_user, c.session.lower(), c.window.lower(), c.pane_id))


def build_snapshot(lines: int = DEFAULT_LINES) -> dict[str, object]:
    cards = collect_cards(lines=lines)
    counts: dict[str, int] = {}
    for card in cards:
        counts[card.state] = counts.get(card.state, 0) + 1
    return {
        "generated_at": time.time(),
        "counts": counts,
        "agents": [asdict(card) for card in cards],
    }


HTML_PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CAO Dashboard</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #111417;
      --panel: #191d22;
      --panel-2: #20262d;
      --text: #eef2f5;
      --muted: #9ba8b5;
      --line: #303842;
      --ready: #d6b24c;
      --working: #46b37b;
      --blocked: #e06666;
      --idle: #78a6d8;
      --missing: #a66ce0;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      position: sticky;
      top: 0;
      z-index: 2;
      background: rgba(17, 20, 23, .96);
      border-bottom: 1px solid var(--line);
      padding: 14px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 { margin: 0; font-size: 18px; font-weight: 650; }
    .meta { color: var(--muted); font-size: 12px; display: flex; gap: 12px; flex-wrap: wrap; justify-content: flex-end; }
    main { padding: 16px; display: grid; gap: 12px; }
    .summary { display: flex; gap: 8px; flex-wrap: wrap; }
    .pill { border: 1px solid var(--line); border-radius: 999px; padding: 4px 9px; color: var(--muted); background: var(--panel); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 12px; }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      min-width: 0;
    }
    .card.needs-user { border-color: color-mix(in srgb, var(--ready), var(--line) 45%); }
    .card-head {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      padding: 12px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
    }
    .title { min-width: 0; }
    .name { font-weight: 650; overflow-wrap: anywhere; }
    .path { color: var(--muted); font-size: 12px; overflow-wrap: anywhere; margin-top: 2px; }
    .badge {
      align-self: start;
      border-radius: 6px;
      padding: 3px 8px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .02em;
      border: 1px solid currentColor;
    }
    .working { color: var(--working); }
    .ready { color: var(--ready); }
    .blocked { color: var(--blocked); }
    .idle { color: var(--idle); }
    .missing { color: var(--missing); }
    .body {
      padding: 12px;
      display: grid;
      gap: 10px;
      overflow-x: auto;
      min-width: 0;
    }
    .body > div { min-width: 0; }
    .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 3px; }
    .source { color: var(--muted); font-size: 11px; margin-top: 4px; overflow-wrap: anywhere; }
    .line {
      display: block;
      width: max-content;
      min-width: 100%;
      white-space: pre;
      padding-bottom: 2px;
    }
    pre {
      margin: 0;
      padding: 10px;
      background: #0c0f12;
      border: 1px solid var(--line);
      border-radius: 6px;
      color: #cdd6df;
      overflow: visible;
      max-height: 240px;
      width: max-content;
      min-width: 100%;
      white-space: pre;
      font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
    .response-scroll {
      overflow: auto;
      max-width: 100%;
      max-height: 320px;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: #0c0f12;
      padding: 12px;
    }
    .markdown {
      color: #dce5ed;
      overflow-wrap: anywhere;
    }
    .markdown > :first-child { margin-top: 0; }
    .markdown > :last-child { margin-bottom: 0; }
    .markdown h1,
    .markdown h2,
    .markdown h3,
    .markdown h4 {
      margin: 14px 0 8px;
      line-height: 1.2;
      color: var(--text);
      letter-spacing: 0;
    }
    .markdown h1 { font-size: 18px; }
    .markdown h2 { font-size: 16px; }
    .markdown h3,
    .markdown h4 { font-size: 14px; }
    .markdown p { margin: 8px 0; }
    .markdown ul,
    .markdown ol { margin: 8px 0; padding-left: 22px; }
    .markdown li { margin: 3px 0; }
    .markdown code {
      background: #111820;
      border: 1px solid #25303a;
      border-radius: 4px;
      padding: 1px 4px;
      font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
    .markdown pre {
      overflow: auto;
      max-height: none;
      width: auto;
      min-width: 0;
      white-space: pre;
      margin: 10px 0;
    }
    .markdown pre code {
      background: transparent;
      border: 0;
      padding: 0;
    }
    .markdown blockquote {
      margin: 8px 0;
      padding: 4px 0 4px 12px;
      border-left: 3px solid var(--line);
      color: #b8c4cf;
    }
    .markdown table {
      width: max-content;
      min-width: 100%;
      border-collapse: collapse;
      margin: 10px 0;
      font-size: 12px;
    }
    .markdown th,
    .markdown td {
      border: 1px solid var(--line);
      padding: 6px 8px;
      vertical-align: top;
    }
    .markdown th {
      background: #151b21;
      color: var(--text);
      text-align: left;
    }
    .clickable-section {
      cursor: pointer;
      border-radius: 6px;
      outline: none;
    }
    .clickable-section:hover .label,
    .clickable-section:focus-visible .label {
      color: var(--text);
    }
    .clickable-section:focus-visible {
      box-shadow: 0 0 0 2px color-mix(in srgb, var(--idle), transparent 35%);
    }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 10;
      background: rgba(0, 0, 0, .68);
      display: grid;
      place-items: center;
      padding: 20px;
    }
    .modal-backdrop[hidden] { display: none; }
    .modal {
      width: min(1100px, 96vw);
      height: min(760px, 90vh);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      display: grid;
      grid-template-rows: auto 1fr;
      overflow: hidden;
      box-shadow: 0 24px 90px rgba(0, 0, 0, .48);
    }
    .modal-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
    }
    .modal-title { font-weight: 650; min-width: 0; overflow-wrap: anywhere; }
    .modal-close {
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--text);
      background: #12161a;
      padding: 6px 10px;
      font: inherit;
      cursor: pointer;
    }
    .modal-body {
      overflow: auto;
      max-height: none;
      width: auto;
      min-width: 0;
      border: 0;
      border-radius: 0;
      padding: 14px;
      background: #0c0f12;
    }
    .live-dot {
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--working);
      box-shadow: 0 0 0 4px rgba(70, 179, 123, .12);
      display: inline-block;
      margin-right: 6px;
    }
    .live-dot.error {
      background: var(--blocked);
      box-shadow: 0 0 0 4px rgba(224, 102, 102, .12);
    }
  </style>
</head>
<body>
  <header>
    <h1>CAO Dashboard</h1>
    <div class="meta">
      <span><span class="live-dot" id="live-dot"></span><span id="live-status">live</span></span>
      <span id="updated">loading</span>
    </div>
  </header>
  <main>
    <section class="summary" id="summary"></section>
    <section class="grid" id="agents"></section>
  </main>
  <div class="modal-backdrop" id="modal-backdrop" hidden>
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div class="modal-head">
        <div class="modal-title" id="modal-title"></div>
        <button class="modal-close" id="modal-close" type="button">Close</button>
      </div>
      <div class="modal-body markdown" id="modal-body"></div>
    </section>
  </div>
  <script>
    const stateClass = (state) => ["working","ready","blocked","idle","missing"].includes(state) ? state : "idle";
    const esc = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    const scrollPositions = new Map();
    let latestSnapshot = null;
    let openFull = null;

    function cardKey(agent) {
      return agent.id || `${agent.session}:${agent.window}:${agent.pane_id}`;
    }

    function captureScrollPositions() {
      document.querySelectorAll("[data-scroll-key]").forEach(node => {
        scrollPositions.set(node.dataset.scrollKey, { left: node.scrollLeft, top: node.scrollTop });
      });
    }

    function restoreScrollPositions() {
      document.querySelectorAll("[data-scroll-key]").forEach(node => {
        const pos = scrollPositions.get(node.dataset.scrollKey);
        if (!pos) return;
        node.scrollLeft = pos.left;
        node.scrollTop = pos.top;
      });
    }

    function inlineMarkdown(value) {
      return esc(value)
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*{2}([^*]+)\*{2}/g, "<strong>$1</strong>");
    }

    function isTableSeparator(line) {
      return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
    }

    function splitTableRow(line) {
      return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(cell => cell.trim());
    }

    function renderMarkdown(text) {
      const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
      const out = [];
      let i = 0;
      while (i < lines.length) {
        const line = lines[i];
        if (!line.trim()) {
          i += 1;
          continue;
        }
        const fence = line.match(/^```(.*)$/);
        if (fence) {
          const code = [];
          i += 1;
          while (i < lines.length && !/^```/.test(lines[i])) {
            code.push(lines[i]);
            i += 1;
          }
          if (i < lines.length) i += 1;
          out.push(`<pre><code>${esc(code.join("\n"))}</code></pre>`);
          continue;
        }
        if (line.includes("|") && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
          const headers = splitTableRow(line);
          i += 2;
          const rows = [];
          while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
            rows.push(splitTableRow(lines[i]));
            i += 1;
          }
          out.push(`<table><thead><tr>${headers.map(cell => `<th>${inlineMarkdown(cell)}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${inlineMarkdown(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table>`);
          continue;
        }
        const heading = line.match(/^(#{1,4})\s+(.+)$/);
        if (heading) {
          const level = heading[1].length;
          out.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
          i += 1;
          continue;
        }
        if (/^\s*>\s?/.test(line)) {
          const quote = [];
          while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
            quote.push(lines[i].replace(/^\s*>\s?/, ""));
            i += 1;
          }
          out.push(`<blockquote>${quote.map(inlineMarkdown).join("<br>")}</blockquote>`);
          continue;
        }
        if (/^\s*[-*]\s+/.test(line)) {
          const items = [];
          while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
            items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
            i += 1;
          }
          out.push(`<ul>${items.map(item => `<li>${inlineMarkdown(item)}</li>`).join("")}</ul>`);
          continue;
        }
        if (/^\s*\d+[.)]\s+/.test(line)) {
          const items = [];
          while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
            items.push(lines[i].replace(/^\s*\d+[.)]\s+/, ""));
            i += 1;
          }
          out.push(`<ol>${items.map(item => `<li>${inlineMarkdown(item)}</li>`).join("")}</ol>`);
          continue;
        }
        const paragraph = [];
        while (
          i < lines.length &&
          lines[i].trim() &&
          !/^```/.test(lines[i]) &&
          !/^(#{1,4})\s+/.test(lines[i]) &&
          !/^\s*>\s?/.test(lines[i]) &&
          !/^\s*[-*]\s+/.test(lines[i]) &&
          !/^\s*\d+[.)]\s+/.test(lines[i]) &&
          !(lines[i].includes("|") && i + 1 < lines.length && isTableSeparator(lines[i + 1]))
        ) {
          paragraph.push(lines[i]);
          i += 1;
        }
        out.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`);
      }
      return out.join("");
    }

    function modalPayload(agent, field) {
      if (field === "runner") return { title: `${agent.session}:${agent.window} - Runner / command`, body: `${agent.runner || ""} / ${agent.command || ""}` };
      if (field === "last_response") return { title: `${agent.session}:${agent.window} - Last response`, body: agent.last_response || "" };
      return { title: `${agent.session}:${agent.window}`, body: "" };
    }

    function findAgent(id) {
      return latestSnapshot?.agents?.find(agent => cardKey(agent) === id);
    }

    function agentContentKey(agent) {
      return JSON.stringify({
        id: agent.id,
        session: agent.session,
        window: agent.window,
        pane_id: agent.pane_id,
        runner: agent.runner,
        state: agent.state,
        needs_user: agent.needs_user,
        cwd: agent.cwd,
        command: agent.command,
        last_response: agent.last_response,
        last_response_source: agent.last_response_source
      });
    }

    function htmlToElement(html) {
      const template = document.createElement("template");
      template.innerHTML = html.trim();
      return template.content.firstElementChild;
    }

    function agentHtml(agent) {
      const key = esc(cardKey(agent));
      const cls = stateClass(agent.state);
      const lastResponse = agent.last_response ? `<div class="clickable-section" role="button" tabindex="0" data-full-agent="${key}" data-full-field="last_response" title="Click to show full text"><div class="label">Last response</div><div class="response-scroll markdown" data-scroll-key="${key}:last-response">${renderMarkdown(agent.last_response)}</div><div class="source">${esc(agent.last_response_source || "")}</div></div>` : "";
      return `<article class="card ${agent.needs_user ? "needs-user" : ""}">
        <div class="card-head">
          <div class="title">
            <div class="name">${esc(agent.session)}:${esc(agent.window)} <span class="path">${esc(agent.pane_id)}</span></div>
            <div class="path">${esc(agent.cwd)}</div>
          </div>
          <div class="badge ${cls}">${esc(agent.state)}</div>
        </div>
        <div class="body">
          ${lastResponse}
          <div class="clickable-section" role="button" tabindex="0" data-full-agent="${key}" data-full-field="runner" title="Click to show full text"><div class="label">Runner / command</div><div class="line">${esc(agent.runner)} / ${esc(agent.command)}</div></div>
        </div>
      </article>`;
    }

    function syncModal() {
      if (!openFull) return;
      const agent = findAgent(openFull.agentId);
      if (!agent) return closeModal();
      const payload = modalPayload(agent, openFull.field);
      const body = document.getElementById("modal-body");
      const left = body.scrollLeft;
      const top = body.scrollTop;
      document.getElementById("modal-title").textContent = payload.title;
      body.innerHTML = renderMarkdown(payload.body);
      body.scrollLeft = left;
      body.scrollTop = top;
    }

    function openModal(agentId, field) {
      openFull = { agentId, field };
      syncModal();
      document.getElementById("modal-backdrop").hidden = false;
    }

    function closeModal() {
      openFull = null;
      document.getElementById("modal-backdrop").hidden = true;
    }

    function render(snapshot) {
      latestSnapshot = snapshot;
      captureScrollPositions();
      const total = snapshot.agents.length;
      const counts = snapshot.counts || {};
      document.getElementById("summary").innerHTML = [
        `<span class="pill">${total} total</span>`,
        `<span class="pill">working ${counts.working || 0}</span>`,
        `<span class="pill">ready ${counts.ready || 0}</span>`,
        `<span class="pill">blocked ${counts.blocked || 0}</span>`,
        `<span class="pill">needs user ${snapshot.agents.filter(a => a.needs_user).length}</span>`
      ].join("");
      const agentsEl = document.getElementById("agents");
      const existingByKey = new Map(Array.from(agentsEl.children).map(node => [node.dataset.cardKey, node]));
      const nextCards = snapshot.agents.map(agent => {
        const key = cardKey(agent);
        const contentKey = agentContentKey(agent);
        let card = existingByKey.get(key);
        if (!card || card.dataset.contentKey !== contentKey) {
          card = htmlToElement(agentHtml(agent));
          card.dataset.cardKey = key;
          card.dataset.contentKey = contentKey;
        }
        return card;
      });
      const currentCards = Array.from(agentsEl.children);
      const sameOrder = currentCards.length === nextCards.length && currentCards.every((card, index) => card === nextCards[index]);
      if (!sameOrder) {
        agentsEl.replaceChildren(...nextCards);
      }
      restoreScrollPositions();
      syncModal();
    }
    async function refresh() {
      const dot = document.getElementById("live-dot");
      const status = document.getElementById("live-status");
      try {
        const res = await fetch("/api/state", { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const snapshot = await res.json();
        document.getElementById("updated").textContent = new Date(snapshot.generated_at * 1000).toLocaleTimeString();
        latestSnapshot = snapshot;
        render(snapshot);
        dot.classList.remove("error");
        status.textContent = "live";
      } catch (error) {
        dot.classList.add("error");
        status.textContent = "disconnected";
      }
    }
    document.getElementById("agents").addEventListener("click", event => {
      const target = event.target.closest("[data-full-agent]");
      if (!target) return;
      openModal(target.dataset.fullAgent, target.dataset.fullField);
    });
    document.getElementById("agents").addEventListener("keydown", event => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const target = event.target.closest("[data-full-agent]");
      if (!target) return;
      event.preventDefault();
      openModal(target.dataset.fullAgent, target.dataset.fullField);
    });
    document.getElementById("modal-close").addEventListener("click", closeModal);
    document.getElementById("modal-backdrop").addEventListener("click", event => {
      if (event.target.id === "modal-backdrop") closeModal();
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && openFull) closeModal();
    });
    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "CAODashboard/0.1"

    def do_HEAD(self) -> None:
        if self.path == "/" or self.path.startswith("/?"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if self.path.startswith("/api/state"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        self.send_error(404)

    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/?"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return
        if self.path.startswith("/api/state"):
            snapshot = build_snapshot()
            body = json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def log_message(self, fmt: str, *args: object) -> None:
        if os.environ.get("CAO_WEB_LOGS"):
            super().log_message(fmt, *args)


def serve(host: str, port: int) -> None:
    httpd = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"CAO Dashboard: http://{host}:{httpd.server_port}", flush=True)
    httpd.serve_forever()


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local CAO dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--snapshot", action="store_true", help="print one JSON snapshot and exit")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.snapshot:
        print(json.dumps(build_snapshot(), ensure_ascii=False, indent=2))
        return 0
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
