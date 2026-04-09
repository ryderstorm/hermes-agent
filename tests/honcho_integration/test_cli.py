"""Tests for Honcho CLI helpers."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from plugins.memory.honcho.client import HonchoClientConfig
from plugins.memory.honcho.cli import _resolve_api_key, _validate_connection, cmd_status


class TestResolveApiKey:
    def test_prefers_host_scoped_key(self):
        cfg = {
            "apiKey": "root-key",
            "hosts": {
                "hermes": {
                    "apiKey": "host-key",
                }
            },
        }
        assert _resolve_api_key(cfg) == "host-key"

    def test_falls_back_to_root_key(self):
        cfg = {
            "apiKey": "root-key",
            "hosts": {"hermes": {}},
        }
        assert _resolve_api_key(cfg) == "root-key"

    def test_falls_back_to_env_key(self, monkeypatch):
        monkeypatch.setenv("HONCHO_API_KEY", "env-key")
        assert _resolve_api_key({}) == "env-key"
        monkeypatch.delenv("HONCHO_API_KEY", raising=False)


class TestValidateConnection:
    def test_runs_real_session_validation_path(self):
        cfg = HonchoClientConfig(api_key="test-key", enabled=True, peer_name="damien")
        mock_client = MagicMock()
        mock_manager = MagicMock()

        with (
            patch("plugins.memory.honcho.client.reset_honcho_client") as mock_reset,
            patch("plugins.memory.honcho.client.get_honcho_client", return_value=mock_client) as mock_get_client,
            patch("plugins.memory.honcho.session.HonchoSessionManager", return_value=mock_manager) as mock_manager_cls,
        ):
            _validate_connection(cfg)

        mock_reset.assert_called_once_with()
        mock_get_client.assert_called_once_with(cfg)
        mock_manager_cls.assert_called_once_with(
            honcho=mock_client,
            config=cfg,
            context_tokens=cfg.context_tokens,
        )
        mock_manager.get_or_create.assert_called_once_with(cfg.resolve_session_name())


class TestCmdStatus:
    def test_reports_failed_real_connection_validation(self, capsys):
        cfg = HonchoClientConfig(api_key="test-key", enabled=True, peer_name="damien")

        with (
            patch.dict(sys.modules, {"honcho": MagicMock()}),
            patch("plugins.memory.honcho.cli._read_config", return_value={"apiKey": "test-key"}),
            patch("plugins.memory.honcho.cli._config_path", return_value=Path("/tmp/config.json")),
            patch("plugins.memory.honcho.client.HonchoClientConfig.from_global_config", return_value=cfg),
            patch("plugins.memory.honcho.cli._validate_connection", side_effect=RuntimeError("boom")),
        ):
            cmd_status(SimpleNamespace())

        output = capsys.readouterr().out
        assert "Connection... FAILED (boom)" in output
