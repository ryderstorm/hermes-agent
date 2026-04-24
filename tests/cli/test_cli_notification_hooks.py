import subprocess
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import cli as cli_module
from cli import HermesCLI
from hermes_cli.plugins import VALID_HOOKS


class _FakeBuffer:
    def __init__(self, text="", cursor_position=None):
        self.text = text
        self.cursor_position = len(text) if cursor_position is None else cursor_position

    def reset(self, append_to_history=False):
        self.text = ""
        self.cursor_position = 0


def _make_cli_stub():
    cli = HermesCLI.__new__(HermesCLI)
    cli._approval_state = None
    cli._approval_deadline = 0
    cli._approval_lock = threading.Lock()
    cli._sudo_state = None
    cli._sudo_deadline = 0
    cli._clarify_state = None
    cli._clarify_deadline = 0
    cli._clarify_freetext = False
    cli._modal_input_snapshot = None
    cli._invalidate = MagicMock()
    cli._app = SimpleNamespace(invalidate=MagicMock(), current_buffer=_FakeBuffer())
    cli.agent = SimpleNamespace(session_id="session-123")
    cli.session_id = "session-123"
    cli.platform = "cli"
    cli.notification_hook_enabled = True
    cli.notification_hook_script = "/tmp/hermes-notify"
    cli.notification_hook_timeout_seconds = 5
    cli._voice_mode = False
    cli._voice_continuous = False
    cli.bell_on_complete = False
    return cli


def test_notification_hooks_registered_in_valid_hooks():
    assert "on_clarify" in VALID_HOOKS
    assert "on_sudo_prompt" in VALID_HOOKS
    assert "on_approval_request" in VALID_HOOKS
    assert "on_task_complete" in VALID_HOOKS


class _FakeThread:
    def __init__(self, *, target=None, args=(), kwargs=None, daemon=None, name=None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.daemon = daemon
        self.name = name
        self.started = False

    def start(self):
        self.started = True


def _configure_fake_thread(fake_thread, **kwargs):
    fake_thread.target = kwargs.get("target")
    fake_thread.args = kwargs.get("args", ())
    fake_thread.kwargs = kwargs.get("kwargs", {})
    fake_thread.daemon = kwargs.get("daemon")
    fake_thread.name = kwargs.get("name")
    return fake_thread


@patch("subprocess.run")
@patch("hermes_cli.plugins.invoke_hook")
@patch("cli.threading.Thread")
def test_emit_cli_notification_event_dispatches_prompt_delivery_on_background_thread(
    mock_thread_ctor, mock_invoke_hook, mock_run, monkeypatch, tmp_path
):
    cli = _make_cli_stub()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))
    fake_thread = _FakeThread()
    mock_thread_ctor.side_effect = lambda **kwargs: _configure_fake_thread(fake_thread, **kwargs)

    cli._emit_cli_notification_event(
        "on_clarify",
        {
            "preview": "  This   is\n\nvery long  " + ("x" * 200),
            "choices_count": 2,
            "task_id": "task-1",
        },
    )

    mock_invoke_hook.assert_not_called()
    mock_run.assert_not_called()
    assert fake_thread.started is True
    assert fake_thread.daemon is True
    assert fake_thread.name == "cli-notify-on_clarify"
    assert fake_thread.target == cli._deliver_cli_notification_event
    assert fake_thread.args[0] == "on_clarify"
    payload = fake_thread.args[1]
    assert payload["session_id"] == "session-123"
    assert payload["platform"] == "cli"
    assert payload["cwd"] == str(workspace)
    assert payload["task_id"] == "task-1"
    assert payload["choices_count"] == 2
    assert "  " not in payload["preview"]
    assert "\n" not in payload["preview"]
    assert payload["preview"].endswith("…")
    assert len(payload["preview"]) <= 160


@patch("cli.threading.Thread")
def test_emit_cli_notification_event_delivers_task_complete_synchronously(mock_thread_ctor, monkeypatch, tmp_path):
    cli = _make_cli_stub()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))

    with patch.object(cli, "_deliver_cli_notification_event") as mock_deliver:
        cli._emit_cli_notification_event(
            "on_task_complete",
            {
                "final_response_preview": "done   now\n" + ("x" * 200),
                "final_response_length": 209,
            },
        )

    mock_thread_ctor.assert_not_called()
    mock_deliver.assert_called_once()
    event_name, payload = mock_deliver.call_args.args
    assert event_name == "on_task_complete"
    assert payload["session_id"] == "session-123"
    assert payload["platform"] == "cli"
    assert payload["cwd"] == str(workspace)
    assert payload["final_response_length"] == 209
    assert "\n" not in payload["final_response_preview"]
    assert "  " not in payload["final_response_preview"]
    assert payload["final_response_preview"].endswith("…")
    assert len(payload["final_response_preview"]) <= 160


def test_notification_effective_cwd_falls_back_when_terminal_cwd_is_invalid(monkeypatch, tmp_path):
    cli = _make_cli_stub()
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    missing = tmp_path / "missing"
    monkeypatch.chdir(fallback)
    monkeypatch.setenv("TERMINAL_CWD", str(missing))

    assert cli._notification_effective_cwd() == str(fallback)


@patch("subprocess.run")
@patch("hermes_cli.plugins.invoke_hook")
def test_deliver_cli_notification_event_invokes_hook_and_script_with_terminal_cwd(mock_invoke_hook, mock_run, monkeypatch, tmp_path):
    cli = _make_cli_stub()
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    script = tmp_path / "hermes-notify"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    cli.notification_hook_script = str(script)
    monkeypatch.setenv("TERMINAL_CWD", str(worktree))

    cli._deliver_cli_notification_event(
        "on_clarify",
        {
            "session_id": "session-123",
            "platform": "cli",
            "cwd": str(worktree),
            "preview": "hello there",
        },
    )

    hook_name = mock_invoke_hook.call_args.args[0]
    payload = mock_invoke_hook.call_args.kwargs
    assert hook_name == "on_clarify"
    assert payload["cwd"] == str(worktree)

    mock_run.assert_called_once()
    argv = mock_run.call_args.args[0]
    assert argv == [str(script), "on_clarify"]
    assert mock_run.call_args.kwargs["timeout"] == 5
    assert mock_run.call_args.kwargs["cwd"] == str(worktree)
    assert '"session_id": "session-123"' in mock_run.call_args.kwargs["input"]


@patch.object(cli_module, "_cprint")
@patch.object(HermesCLI, "_emit_cli_notification_event")
def test_clarify_callback_emits_on_clarify_before_waiting(mock_emit, _mock_cprint):
    cli = _make_cli_stub()
    result = {}

    def _run_callback():
        result["value"] = cli._clarify_callback("Need input?", ["A", "B"])

    thread = threading.Thread(target=_run_callback, daemon=True)
    thread.start()

    deadline = time.time() + 2
    while cli._clarify_state is None and time.time() < deadline:
        time.sleep(0.01)

    assert cli._clarify_state is not None
    mock_emit.assert_called_once_with(
        "on_clarify",
        {"preview": "Need input?", "choices_count": 2},
    )

    cli._clarify_state["response_queue"].put("A")
    thread.join(timeout=2)
    assert result["value"] == "A"


@patch.object(cli_module, "_cprint")
@patch.object(HermesCLI, "_emit_cli_notification_event")
def test_sudo_callback_emits_on_sudo_prompt_before_waiting(mock_emit, _mock_cprint):
    cli = _make_cli_stub()
    result = {}

    def _run_callback():
        result["value"] = cli._sudo_password_callback()

    thread = threading.Thread(target=_run_callback, daemon=True)
    thread.start()

    deadline = time.time() + 2
    while cli._sudo_state is None and time.time() < deadline:
        time.sleep(0.01)

    assert cli._sudo_state is not None
    mock_emit.assert_called_once_with("on_sudo_prompt", {})

    cli._sudo_state["response_queue"].put("secret")
    thread.join(timeout=2)
    assert result["value"] == "secret"


@patch.object(cli_module, "_cprint")
@patch.object(HermesCLI, "_emit_cli_notification_event")
def test_approval_callback_emits_on_approval_request_before_waiting(mock_emit, _mock_cprint):
    cli = _make_cli_stub()
    result = {}

    def _run_callback():
        result["value"] = cli._approval_callback("rm -rf /tmp/x", "dangerous")

    thread = threading.Thread(target=_run_callback, daemon=True)
    thread.start()

    deadline = time.time() + 2
    while cli._approval_state is None and time.time() < deadline:
        time.sleep(0.01)

    assert cli._approval_state is not None
    mock_emit.assert_called_once_with(
        "on_approval_request",
        {"preview": "rm -rf /tmp/x", "description": "dangerous", "choices_count": 4},
    )

    cli._approval_state["response_queue"].put("deny")
    thread.join(timeout=2)
    assert result["value"] == "deny"


@patch.object(HermesCLI, "_emit_cli_notification_event")
def test_emit_task_complete_event_suppressed_for_continuous_voice(mock_emit):
    cli = _make_cli_stub()
    cli._voice_mode = True
    cli._voice_continuous = True

    cli._emit_task_complete_event("done", interrupted=False)

    mock_emit.assert_not_called()


@patch.object(HermesCLI, "_emit_cli_notification_event")
def test_emit_task_complete_event_emits_small_payload_for_foreground_completion(mock_emit, monkeypatch):
    cli = _make_cli_stub()
    monkeypatch.setenv("TERMINAL_CWD", "/tmp/project")

    raw_response = "hello world\n" + ("x" * 200)
    cli._emit_task_complete_event(raw_response, interrupted=False)

    mock_emit.assert_called_once()
    hook_name = mock_emit.call_args.args[0]
    payload = mock_emit.call_args.args[1]
    assert hook_name == "on_task_complete"
    assert "cwd" not in payload
    assert "interrupted" not in payload
    assert payload["final_response_length"] == len(raw_response)
    # Preview is passed raw; sanitization happens inside _emit_cli_notification_event.
    assert payload["final_response_preview"] == raw_response


@patch.object(HermesCLI, "_emit_cli_notification_event")
def test_emit_task_complete_event_suppressed_when_interrupted(mock_emit):
    cli = _make_cli_stub()

    cli._emit_task_complete_event("partial", interrupted=True)

    mock_emit.assert_not_called()


def test_task_complete_interrupted_state_treats_abandoned_interrupt_as_interrupted():
    cli = _make_cli_stub()

    assert cli._task_complete_was_interrupted(None, "follow-up prompt") is True
    assert cli._task_complete_was_interrupted({"interrupted": True}, None) is True
    assert cli._task_complete_was_interrupted({"interrupted": False}, None) is False


@patch("subprocess.run")
def test_run_notification_hook_script_noop_when_disabled(mock_run):
    cli = _make_cli_stub()
    cli.notification_hook_enabled = False

    cli._run_notification_hook_script(
        "on_task_complete",
        {"session_id": "session-123", "platform": "cli", "cwd": "/tmp/x"},
    )

    mock_run.assert_not_called()


@patch("subprocess.run")
def test_run_notification_hook_script_noop_when_script_empty(mock_run):
    cli = _make_cli_stub()
    cli.notification_hook_enabled = True
    cli.notification_hook_script = "   "

    cli._run_notification_hook_script(
        "on_task_complete",
        {"session_id": "session-123", "platform": "cli", "cwd": "/tmp/x"},
    )

    mock_run.assert_not_called()


def test_emit_task_complete_event_sanitizes_preview_before_synchronous_delivery(monkeypatch, tmp_path):
    cli = _make_cli_stub()
    workspace = tmp_path / "project"
    workspace.mkdir()
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))

    raw_response = "hello   world\n\n" + ("x" * 200)

    with patch.object(cli, "_deliver_cli_notification_event") as mock_deliver:
        cli._emit_task_complete_event(raw_response, interrupted=False)

    mock_deliver.assert_called_once()
    event_name, payload = mock_deliver.call_args.args
    assert event_name == "on_task_complete"
    assert payload["session_id"] == "session-123"
    assert payload["platform"] == "cli"
    assert payload["cwd"] == str(workspace)
    assert "interrupted" not in payload
    assert payload["final_response_length"] == len(raw_response)
    assert "\n" not in payload["final_response_preview"]
    assert "  " not in payload["final_response_preview"]
    assert payload["final_response_preview"].endswith("…")
    assert len(payload["final_response_preview"]) <= 160


@patch("cli.threading.Thread")
def test_emit_cli_notification_event_redacts_and_caps_sensitive_payload_fields(mock_thread_ctor, monkeypatch):
    cli = _make_cli_stub()
    monkeypatch.delenv("TERMINAL_CWD", raising=False)
    fake_thread = _FakeThread()
    mock_thread_ctor.side_effect = lambda **kwargs: _configure_fake_thread(fake_thread, **kwargs)
    secret = "sk-1234567890abcdefghijklmnopqrstuvwxyz"

    cli._emit_cli_notification_event(
        "on_approval_request",
        {
            "preview": f"OPENAI_API_KEY={secret} run thing",
            "description": f"desc token={secret} " + ("x" * 1200),
            "choices_count": 4,
        },
    )

    payload = fake_thread.args[1]
    assert secret not in payload["preview"]
    assert secret not in payload["description"]
    assert len(payload["description"]) <= 500


@patch.object(cli_module.logger, "debug")
def test_sanitize_notification_preview_logs_and_fails_closed_when_redaction_fails(mock_debug):
    cli = _make_cli_stub()
    secret = "sk-123...wxyz"

    with patch("agent.redact.redact_sensitive_text", side_effect=RuntimeError("boom")):
        sanitized = cli._sanitize_notification_preview(
            f"OPENAI_API_KEY={secret} should not leak"
        )

    assert sanitized == "[notification text unavailable: redaction failed]"
    assert secret not in sanitized
    mock_debug.assert_called_with(
        "Failed to redact CLI notification text; emitting placeholder",
        exc_info=True,
    )


@patch("subprocess.run")
def test_run_notification_hook_script_rejects_relative_script_path(mock_run):
    cli = _make_cli_stub()
    cli.notification_hook_enabled = True
    cli.notification_hook_script = "bin/hermes-notify"

    cli._run_notification_hook_script(
        "on_task_complete",
        {"session_id": "session-123", "platform": "cli", "cwd": "/tmp/x"},
    )

    mock_run.assert_not_called()


@patch.object(cli_module.logger, "debug")
@patch("subprocess.run")
def test_deliver_cli_notification_event_swallows_script_launch_failures(mock_run, mock_debug, tmp_path):
    cli = _make_cli_stub()
    script = tmp_path / "hermes-notify"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    cli.notification_hook_script = str(script)
    mock_run.side_effect = FileNotFoundError("missing")

    cli._deliver_cli_notification_event("on_task_complete", {"session_id": "session-123"})

    mock_debug.assert_any_call(
        "Failed to run CLI notification hook script for %s",
        "on_task_complete",
        exc_info=True,
    )


@patch.object(cli_module.logger, "debug")
@patch("subprocess.run")
def test_deliver_cli_notification_event_swallows_script_timeouts(mock_run, mock_debug, tmp_path):
    cli = _make_cli_stub()
    script = tmp_path / "hermes-notify"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    cli.notification_hook_script = str(script)
    mock_run.side_effect = subprocess.TimeoutExpired(cmd=[str(script)], timeout=5)

    cli._deliver_cli_notification_event("on_task_complete", {"session_id": "session-123"})

    mock_debug.assert_any_call(
        "Failed to run CLI notification hook script for %s",
        "on_task_complete",
        exc_info=True,
    )


@patch.object(cli_module.logger, "debug")
@patch("subprocess.run")
def test_run_notification_hook_script_logs_nonzero_exit_with_context(mock_run, mock_debug, tmp_path):
    cli = _make_cli_stub()
    cli.notification_hook_enabled = True
    script = tmp_path / "hermes-notify"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    cli.notification_hook_script = str(script)
    cli.notification_hook_timeout_seconds = 9
    mock_run.return_value = SimpleNamespace(returncode=7, stderr="boom" * 200)

    cli._run_notification_hook_script(
        "on_task_complete",
        {"session_id": "session-123", "platform": "cli", "cwd": "/tmp/x"},
    )

    mock_run.assert_called_once()
    argv = mock_run.call_args.args[0]
    assert argv == [str(script), "on_task_complete"]
    assert mock_run.call_args.kwargs["timeout"] == 9

    mock_debug.assert_called_once()
    log_args = mock_debug.call_args.args
    assert log_args[0] == "CLI notification hook script %s exited non-zero for %s (rc=%s): %s"
    assert log_args[1] == str(script)
    assert log_args[2] == "on_task_complete"
    assert log_args[3] == 7
    assert len(log_args[4]) == 500
    assert log_args[4] == ("boom" * 200)[:500]
