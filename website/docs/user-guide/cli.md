---
sidebar_position: 1
title: "CLI Interface"
description: "Master the Hermes Agent terminal interface — commands, keybindings, personalities, and more"
---

# CLI Interface

Hermes Agent's CLI is a full terminal user interface (TUI) — not a web UI. It features multiline editing, slash-command autocomplete, conversation history, interrupt-and-redirect, and streaming tool output. Built for people who live in the terminal.

:::tip
Hermes also ships a modern TUI with modal overlays, mouse selection, and non-blocking input. Launch it with `hermes --tui` — see the [TUI](tui.md) guide.
:::

## Running the CLI

```bash
# Start an interactive session (default)
hermes

# Single query mode (non-interactive)
hermes chat -q "Hello"

# With a specific model
hermes chat --model "anthropic/claude-sonnet-4"

# With a specific provider
hermes chat --provider nous        # Use Nous Portal
hermes chat --provider openrouter  # Force OpenRouter

# With specific toolsets
hermes chat --toolsets "web,terminal,skills"

# Start with one or more skills preloaded
hermes -s hermes-agent-dev,github-auth
hermes chat -s github-pr-workflow -q "open a draft PR"

# Resume previous sessions
hermes --continue             # Resume the most recent CLI session (-c)
hermes --resume <session_id>  # Resume a specific session by ID (-r)

# Verbose mode (debug output)
hermes chat --verbose

# Isolated git worktree (for running multiple agents in parallel)
hermes -w                         # Interactive mode in worktree
hermes -w -q "Fix issue #123"     # Single query in worktree
```

## Interface Layout

<img className="docs-terminal-figure" src="/img/docs/cli-layout.svg" alt="Stylized preview of the Hermes CLI layout showing the banner, conversation area, and fixed input prompt." />
<p className="docs-figure-caption">The Hermes CLI banner, conversation stream, and fixed input prompt rendered as a stable docs figure instead of fragile text art.</p>

The welcome banner shows your model, terminal backend, working directory, available tools, and installed skills at a glance.

### Status Bar

A persistent status bar sits above the input area, updating in real time:

```
 ⚕ claude-sonnet-4-20250514 │ 12.4K/200K │ [██████░░░░] 6% │ $0.06 │ 15m
```

| Element | Description |
|---------|-------------|
| Model name | Current model (truncated if longer than 26 chars) |
| Token count | Context tokens used / max context window |
| Context bar | Visual fill indicator with color-coded thresholds |
| Cost | Estimated session cost (or `n/a` for unknown/zero-priced models) |
| Duration | Elapsed session time |

The bar adapts to terminal width — full layout at ≥ 76 columns, compact at 52–75, minimal (model + duration only) below 52.

**Context color coding:**

| Color | Threshold | Meaning |
|-------|-----------|---------|
| Green | < 50% | Plenty of room |
| Yellow | 50–80% | Getting full |
| Orange | 80–95% | Approaching limit |
| Red | ≥ 95% | Near overflow — consider `/compress` |

Use `/usage` for a detailed breakdown including per-category costs (input vs output tokens).

### Session Resume Display

When resuming a previous session (`hermes -c` or `hermes --resume <id>`), a "Previous Conversation" panel appears between the banner and the input prompt, showing a compact recap of the conversation history. See [Sessions — Conversation Recap on Resume](sessions.md#conversation-recap-on-resume) for details and configuration.

## Keybindings

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Alt+Enter` or `Ctrl+J` | New line (multi-line input) |
| `Alt+V` | Paste an image from the clipboard when supported by the terminal |
| `Ctrl+V` | Paste text and opportunistically attach clipboard images |
| `Ctrl+B` | Start/stop voice recording when voice mode is enabled (`voice.record_key`, default: `ctrl+b`) |
| `Ctrl+C` | Interrupt agent (double-press within 2s to force exit) |
| `Ctrl+D` | Exit |
| `Ctrl+Z` | Suspend Hermes to background (Unix only). Run `fg` in the shell to resume. |
| `Tab` | Accept auto-suggestion (ghost text) or autocomplete slash commands |

## Slash Commands

Type `/` to see the autocomplete dropdown. Hermes supports a large set of CLI slash commands, dynamic skill commands, and user-defined quick commands.

Common examples:

| Command | Description |
|---------|-------------|
| `/help` | Show command help |
| `/model` | Show or change the current model |
| `/tools` | List currently available tools |
| `/skills browse` | Browse the skills hub and official optional skills |
| `/background <prompt>` | Run a prompt in a separate background session |
| `/skin` | Show or switch the active CLI skin |
| `/voice on` | Enable CLI voice mode (press `Ctrl+B` to record) |
| `/voice tts` | Toggle spoken playback for Hermes replies |
| `/reasoning high` | Increase reasoning effort |
| `/title My Session` | Name the current session |

For the full built-in CLI and messaging lists, see [Slash Commands Reference](../reference/slash-commands.md).

For setup, providers, silence tuning, and messaging/Discord voice usage, see [Voice Mode](features/voice-mode.md).

:::tip
Commands are case-insensitive — `/HELP` works the same as `/help`. Installed skills also become slash commands automatically.
:::

## Quick Commands

You can define custom commands that run shell commands instantly without invoking the LLM. These work in both the CLI and messaging platforms (Telegram, Discord, etc.).

```yaml
# ~/.hermes/config.yaml
quick_commands:
  status:
    type: exec
    command: systemctl status hermes-agent
  gpu:
    type: exec
    command: nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
```

Then type `/status` or `/gpu` in any chat. See the [Configuration guide](/docs/user-guide/configuration#quick-commands) for more examples.

## Preloading Skills at Launch

If you already know which skills you want active for the session, pass them at launch time:

```bash
hermes -s hermes-agent-dev,github-auth
hermes chat -s github-pr-workflow -s github-auth
```

Hermes loads each named skill into the session prompt before the first turn. The same flag works in interactive mode and single-query mode.

## Skill Slash Commands

Every installed skill in `~/.hermes/skills/` is automatically registered as a slash command. The skill name becomes the command:

```
/gif-search funny cats
/axolotl help me fine-tune Llama 3 on my dataset
/github-pr-workflow create a PR for the auth refactor

# Just the skill name loads it and lets the agent ask what you need:
/excalidraw
```

## Personalities

Set a predefined personality to change the agent's tone:

```
/personality pirate
/personality kawaii
/personality concise
```

Built-in personalities include: `helpful`, `concise`, `technical`, `creative`, `teacher`, `kawaii`, `catgirl`, `pirate`, `shakespeare`, `surfer`, `noir`, `uwu`, `philosopher`, `hype`.

You can also define custom personalities in `~/.hermes/config.yaml`:

```yaml
personalities:
  helpful: "You are a helpful, friendly AI assistant."
  kawaii: "You are a kawaii assistant! Use cute expressions..."
  pirate: "Arrr! Ye be talkin' to Captain Hermes..."
  # Add your own!
```

## Multi-line Input

There are two ways to enter multi-line messages:

1. **`Alt+Enter` or `Ctrl+J`** — inserts a new line
2. **Backslash continuation** — end a line with `\` to continue:

```
❯ Write a function that:\
  1. Takes a list of numbers\
  2. Returns the sum
```

:::info
Pasting multi-line text is supported — use `Alt+Enter` or `Ctrl+J` to insert newlines, or simply paste content directly.
:::

## Interrupting the Agent

You can interrupt the agent at any point:

- **Type a new message + Enter** while the agent is working — it interrupts and processes your new instructions
- **`Ctrl+C`** — interrupt the current operation (press twice within 2s to force exit)
- In-progress terminal commands are killed immediately (SIGTERM, then SIGKILL after 1s)
- Multiple messages typed during interrupt are combined into one prompt

### Busy Input Mode

The `display.busy_input_mode` config key controls what happens when you press Enter while the agent is working:

| Mode | Behavior |
|------|----------|
| `"interrupt"` (default) | Your message interrupts the current operation and is processed immediately |
| `"queue"` | Your message is silently queued and sent as the next turn after the agent finishes |

```yaml
# ~/.hermes/config.yaml
display:
  busy_input_mode: "queue"   # or "interrupt" (default)
```

Queue mode is useful when you want to prepare follow-up messages without accidentally canceling in-flight work. Unknown values fall back to `"interrupt"`.

### Suspending to Background

On Unix systems, press **`Ctrl+Z`** to suspend Hermes to the background — just like any terminal process. The shell prints a confirmation:

```
Hermes Agent has been suspended. Run `fg` to bring Hermes Agent back.
```

Type `fg` in your shell to resume the session exactly where you left off. This is not supported on Windows.

## Tool Progress Display

The CLI shows animated feedback as the agent works:

**Thinking animation** (during API calls):
```
  ◜ (｡•́︿•̀｡) pondering... (1.2s)
  ◠ (⊙_⊙) contemplating... (2.4s)
  ✧٩(ˊᗜˋ*)و✧ got it! (3.1s)
```

**Tool execution feed:**
```
  ┊ 💻 terminal `ls -la` (0.3s)
  ┊ 🔍 web_search (1.2s)
  ┊ 📄 web_extract (2.1s)
```

Cycle through display modes with `/verbose`: `off → new → all → verbose`. This command can also be enabled for messaging platforms — see [configuration](/docs/user-guide/configuration#display-settings).

### Tool Preview Length

The `display.tool_preview_length` config key controls the maximum number of characters shown in tool call preview lines (e.g. file paths, terminal commands). The default is `0`, which means no limit — full paths and commands are shown.

```yaml
# ~/.hermes/config.yaml
display:
  tool_preview_length: 80   # Truncate tool previews to 80 chars (0 = no limit)
```

This is useful on narrow terminals or when tool arguments contain very long file paths.

## Session Management

### Resuming Sessions

When you exit a CLI session, a resume command is printed:

```
Resume this session with:
  hermes --resume 20260225_143052_a1b2c3

Session:        20260225_143052_a1b2c3
Duration:       12m 34s
Messages:       28 (5 user, 18 tool calls)
```

Resume options:

```bash
hermes --continue                          # Resume the most recent CLI session
hermes -c                                  # Short form
hermes -c "my project"                     # Resume a named session (latest in lineage)
hermes --resume 20260225_143052_a1b2c3     # Resume a specific session by ID
hermes --resume "refactoring auth"         # Resume by title
hermes -r 20260225_143052_a1b2c3           # Short form
```

Resuming restores the full conversation history from SQLite. The agent sees all previous messages, tool calls, and responses — just as if you never left.

Use `/title My Session Name` inside a chat to name the current session, or `hermes sessions rename <id> <title>` from the command line. Use `hermes sessions list` to browse past sessions.

### Session Storage

CLI sessions are stored in Hermes's SQLite state database under `~/.hermes/state.db`. The database keeps:

- session metadata (ID, title, timestamps, token counters)
- message history
- lineage across compressed/resumed sessions
- full-text search indexes used by `session_search`

Some messaging adapters also keep per-platform transcript files alongside the database, but the CLI itself resumes from the SQLite session store.

### Context Compression

Long conversations are automatically summarized when approaching context limits:

```yaml
# In ~/.hermes/config.yaml
compression:
  enabled: true
  threshold: 0.50    # Compress at 50% of context limit by default

# Summarization model configured under auxiliary:
auxiliary:
  compression:
    model: "google/gemini-3-flash-preview"  # Model used for summarization
```

When compression triggers, middle turns are summarized while the first 3 and last 4 turns are always preserved.

## Background Sessions

Run a prompt in a separate background session while continuing to use the CLI for other work:

```
/background Analyze the logs in /var/log and summarize any errors from today
```

Hermes immediately confirms the task and gives you back the prompt:

```
🔄 Background task #1 started: "Analyze the logs in /var/log and summarize..."
   Task ID: bg_143022_a1b2c3
```

### How It Works

Each `/background` prompt spawns a **completely separate agent session** in a daemon thread:

- **Isolated conversation** — the background agent has no knowledge of your current session's history. It receives only the prompt you provide.
- **Same configuration** — the background agent inherits your model, provider, toolsets, reasoning settings, and fallback model from the current session.
- **Non-blocking** — your foreground session stays fully interactive. You can chat, run commands, or even start more background tasks.
- **Multiple tasks** — you can run several background tasks simultaneously. Each gets a numbered ID.

### Results

When a background task finishes, the result appears as a panel in your terminal:

```
╭─ ⚕ Hermes (background #1) ──────────────────────────────────╮
│ Found 3 errors in syslog from today:                         │
│ 1. OOM killer invoked at 03:22 — killed process nginx        │
│ 2. Disk I/O error on /dev/sda1 at 07:15                      │
│ 3. Failed SSH login attempts from 192.168.1.50 at 14:30      │
╰──────────────────────────────────────────────────────────────╯
```

If the task fails, you'll see an error notification instead. If `display.bell_on_complete` is enabled in your config, the terminal bell rings when the task finishes.

### Use Cases

- **Long-running research** — "/background research the latest developments in quantum error correction" while you work on code
- **File processing** — "/background analyze all Python files in this repo and list any security issues" while you continue a conversation
- **Parallel investigations** — start multiple background tasks to explore different angles simultaneously

:::info
Background sessions do not appear in your main conversation history. They are standalone sessions with their own task ID (e.g., `bg_143022_a1b2c3`).
:::

## CLI Notification Hooks

Hermes can also call a user-owned local script for foreground CLI lifecycle events.

Supported events:
- `on_clarify` — Hermes is blocked on a clarify prompt
- `on_sudo_prompt` — Hermes is waiting for a sudo password
- `on_approval_request` — Hermes is waiting for dangerous-command approval
- `on_task_complete` — the foreground response has finished rendering and control is back to you

Hermes runs your script directly without shell interpolation:
- `argv[1]` = event name
- `stdin` = small JSON payload
- `cwd` = the effective terminal workspace (`TERMINAL_CWD` when set, otherwise the launcher cwd)

Payload fields always present:

| Field | Type | Notes |
| --- | --- | --- |
| `session_id` | string \| null | Active Hermes session id |
| `platform` | string | Always `cli` for this feature |
| `cwd` | string | Effective terminal workspace |

Event-specific fields:

| Event | Extra fields |
| --- | --- |
| `on_clarify` | `preview` (question preview), `choices_count` (omitted for open-ended clarify prompts) |
| `on_sudo_prompt` | none |
| `on_approval_request` | `preview` (command preview), `description`, `choices_count` |
| `on_task_complete` | `final_response_preview`, `final_response_length` |

Hermes does not emit `on_task_complete` for interrupted foreground runs; the event means a visible response finished rendering and control returned to the prompt.

Example payloads:

```json
{
  "session_id": "20260225_143052_a1b2c3",
  "platform": "cli",
  "cwd": "/home/damien/projects/hermes-agent",
  "preview": "Need input?",
  "choices_count": 2
}
```

```json
{
  "session_id": "20260225_143052_a1b2c3",
  "platform": "cli",
  "cwd": "/home/damien/projects/hermes-agent",
  "final_response_preview": "Done — updated the notification hook docs.",
  "final_response_length": 44
}
```

Example config:

```yaml
display:
  notification_hook_enabled: true
  notification_hook_script: /home/you/bin/hermes-notify
  notification_hook_timeout_seconds: 5
```

`notification_hook_script` must resolve to an absolute executable file. `~` is expanded, but relative paths and bare executable names are rejected so hooks cannot change behavior based on the current project directory.

Minimal example script:

```bash
#!/usr/bin/env bash
set -euo pipefail

event="${1:-unknown}"
payload="$(cat)"

case "$event" in
  on_task_complete)
    notify-send "Hermes" "Foreground task complete"
    ;;
  on_clarify)
    notify-send "Hermes" "Hermes is waiting for clarification"
    ;;
esac

printf '%s\n' "$payload" >"${XDG_RUNTIME_DIR:-$HOME/.cache}/hermes-last-event.json"
```

:::warning
Notification payloads may include sensitive snippets from command previews, clarify prompts, approval descriptions, response previews, cwd, and session identifiers. Hermes redacts common secret patterns before delivery, but your notifier should still avoid logging payloads verbatim to shared locations. If you persist payloads for testing, use a private directory and restrictive permissions.
:::

### Test your hook

1. Create a private notifier script, for example `/home/you/bin/hermes-notify`, that appends `argv[1]` and stdin to a file under `$HOME/.cache` or another private directory.
2. Run `chmod +x /home/you/bin/hermes-notify`.
3. Enable `display.notification_hook_enabled`, set `display.notification_hook_script` to the absolute script path, and restart Hermes.
4. Run a foreground non-quiet command such as `hermes --query "say done"`.
5. Confirm the test file contains an `on_task_complete` payload.

Runtime behavior and failure semantics:
- Hermes only emits these hooks for foreground CLI events.
- Prompt-blocking hooks (`on_clarify`, `on_sudo_prompt`, and `on_approval_request`) are delivered asynchronously so Hermes can continue the prompt flow.
- `on_task_complete` is delivered synchronously after the response renders, so completion scripts can delay prompt return by up to `display.notification_hook_timeout_seconds`.
- `display.notification_hook_enabled` gates whether the local script runs.
- `display.notification_hook_script` is executed directly as `[script_path, event_name]` with the JSON payload on stdin; it must be an absolute executable file path after `~` expansion.
- `display.notification_hook_timeout_seconds` applies to the local script subprocess only.
- `preview`, `description`, and `final_response_preview` are redacted, whitespace-collapsed, and length-capped before delivery.
- Plugin hook exceptions, script launch failures, and script timeouts do not interrupt the CLI; Hermes logs them for debugging and continues.
- Hermes does not require a zero exit code from the script.

Example: fuller Linux notifier using `notify-send`

```python
#!/usr/bin/env python3
import json
import os
import subprocess
import sys

TIMEOUT_MS = 10000
APP_NAME = "Hermes"
DESKTOP_ENTRY = "hermes"
EVENTS = {
    "on_clarify": ("Hermes needs clarification", "A clarify prompt is waiting in the CLI."),
    "on_sudo_prompt": ("Hermes needs sudo", "A sudo password prompt is waiting in the CLI."),
    "on_approval_request": ("Hermes needs approval", "A dangerous-command approval prompt is waiting in the CLI."),
    "on_task_complete": ("Hermes finished", "A foreground Hermes task completed."),
}


def compact(value, limit=220):
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def format_cwd(value, limit=120):
    cwd = str(value or "").strip()
    if not cwd:
        return ""
    home = os.path.expanduser("~")
    if cwd.startswith(home):
        cwd = "~" + cwd[len(home):]
    return f"cwd: {compact(cwd, limit)}"


def load_event(argv):
    event = argv[1] if len(argv) > 1 else "hermes-event"
    raw = sys.stdin.read().strip()
    if not raw:
        return event, {}
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {"raw": raw}
    return event, payload if isinstance(payload, dict) else {"raw": payload}


def render(event, payload):
    title, fallback = EVENTS.get(event, ("Hermes notification", event))
    body = (
        compact(payload.get("final_response_preview"))
        or compact(payload.get("preview"))
        or compact(payload.get("raw"))
        or fallback
    )
    cwd = format_cwd(payload.get("cwd"))
    if event == "on_clarify" and isinstance(payload.get("choices_count"), int) and payload["choices_count"] > 0:
        body = f"{body} Choices: {payload['choices_count']}."
    elif event == "on_approval_request":
        description = compact(payload.get("description"), 120)
        if description and description not in body:
            body = f"{body} {description}"
    return title, f"{body}\n{cwd}" if cwd else body


def main(argv):
    event, payload = load_event(argv)
    title, message = render(event, payload)
    subprocess.run(
        [
            "notify-send",
            "-t",
            str(TIMEOUT_MS),
            "--app-name",
            APP_NAME,
            "-h",
            f"string:desktop-entry:{DESKTOP_ENTRY}",
            title,
            message,
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

This feature is intentionally CLI-only and foreground-only. It does not cover `/background`, messaging gateways, or quiet single-query automation.

Non-quiet single-shot runs (`hermes --query "..."` without `--quiet`) still go through the interactive chat render path, so `on_task_complete` fires for them. Only `--quiet` single-shot automation takes a separate path that skips these hooks.

## Quiet Mode

By default, the CLI runs in quiet mode which:
- Suppresses verbose logging from tools
- Enables kawaii-style animated feedback
- Keeps output clean and user-friendly

For debug output:
```bash
hermes chat --verbose
```
