"""Tests for Open WebUI cron delivery helpers."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from cron.openwebui_delivery import (
    OpenWebUIDeliveryError,
    deliver_to_openwebui,
    preflight_openwebui_delivery,
)


class TestDeliverToOpenWebUI:
    def test_posts_new_chat_with_expected_payload(self):
        job = {
            "id": "job-123",
            "name": "Nightly digest",
            "schedule_display": "every 6h",
        }
        fixed_now = datetime(2026, 3, 31, 7, 45, 0, tzinfo=timezone.utc)

        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"id": "row-123", "chat": {"id": "chat-123"}}

        client = MagicMock()
        client.request.return_value = response

        with patch("cron.openwebui_delivery._hermes_now", return_value=fixed_now), \
             patch("cron.openwebui_delivery._new_id", side_effect=["chat-123", "user-123", "assistant-123"]), \
             patch("cron.openwebui_delivery.httpx.Client") as client_cls:
            client_cls.return_value.__enter__.return_value = client

            result = deliver_to_openwebui(
                job,
                "Top priorities for today...",
                config={
                    "cron": {
                        "openwebui": {
                            "base_url": "https://open-webui.example.com/",
                            "api_key": "test-key",
                            "title_template": "{job_name} [{schedule}] – {date}",
                            "user_message_template": "Scheduled task result for {job_name} at {datetime}",
                            "model_name": "hermes-agent",
                        }
                    }
                },
            )

        assert result["chat_id"] == "row-123"
        assert result["chat_payload_id"] == "chat-123"
        client.request.assert_called_once()
        assert client.request.call_args.args[:2] == ("POST", "https://open-webui.example.com/api/v1/chats/new")
        payload = client.request.call_args.kwargs["json"]
        headers = client_cls.call_args.kwargs["headers"]

        assert headers["Authorization"] == "Bearer test-key"
        assert payload["chat"]["title"] == "Nightly digest [every 6h] – 2026-03-31"
        assert payload["chat"]["history"]["currentId"] == "assistant-123"
        assert payload["chat"]["messages"][0]["content"] == (
            "Scheduled task result for Nightly digest at 2026-03-31T07:45:00+00:00"
        )
        assert payload["chat"]["messages"][1]["content"] == "Top priorities for today..."
        assert payload["chat"]["messages"][0]["childrenIds"] == ["assistant-123"]
        assert payload["chat"]["messages"][1]["parentId"] == "user-123"

    def test_uses_job_id_when_name_missing(self):
        job = {"id": "job-123"}
        fixed_now = datetime(2026, 3, 31, 7, 45, 0, tzinfo=timezone.utc)

        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"id": "row-123", "chat": {"id": "chat-123"}}

        client = MagicMock()
        client.request.return_value = response

        with patch("cron.openwebui_delivery._hermes_now", return_value=fixed_now), \
             patch("cron.openwebui_delivery._new_id", side_effect=["chat-123", "user-123", "assistant-123"]), \
             patch("cron.openwebui_delivery.httpx.Client") as client_cls:
            client_cls.return_value.__enter__.return_value = client

            deliver_to_openwebui(
                job,
                "Done.",
                config={
                    "cron": {
                        "openwebui": {
                            "base_url": "https://open-webui.example.com/",
                            "api_key": "test-key",
                        }
                    }
                },
            )

        payload = client.request.call_args.kwargs["json"]
        assert payload["chat"]["title"] == "job-123 – 2026-03-31"
        assert payload["chat"]["messages"][0]["content"] == (
            "Scheduled task result for job-123 at 2026-03-31T07:45:00+00:00"
        )

    def test_requires_base_url_and_api_key(self):
        job = {"id": "job-123", "name": "Nightly digest"}

        with pytest.raises(OpenWebUIDeliveryError, match="base_url"):
            deliver_to_openwebui(job, "content", config={"cron": {"openwebui": {"api_key": "test-key"}}})

        with pytest.raises(OpenWebUIDeliveryError, match="api_key"):
            deliver_to_openwebui(job, "content", config={"cron": {"openwebui": {"base_url": "https://open-webui.example.com"}}})

    def test_rejects_unknown_template_placeholders(self):
        job = {"id": "job-123", "name": "Nightly digest"}

        with pytest.raises(OpenWebUIDeliveryError, match="Unknown placeholder"):
            deliver_to_openwebui(
                job,
                "content",
                config={
                    "cron": {
                        "openwebui": {
                            "base_url": "https://open-webui.example.com",
                            "api_key": "test-key",
                            "title_template": "{unknown}",
                        }
                    }
                },
            )

    def test_preflight_checks_version_and_authenticated_chat_listing(self):
        version_response = MagicMock()
        version_response.raise_for_status.return_value = None
        version_response.json.return_value = {"version": "0.8.12"}

        chats_response = MagicMock()
        chats_response.raise_for_status.return_value = None
        chats_response.json.return_value = [{"id": "chat-1"}, {"id": "chat-2"}]

        client = MagicMock()
        client.request.side_effect = [version_response, chats_response]

        with patch("cron.openwebui_delivery.httpx.Client") as client_cls:
            client_cls.return_value.__enter__.return_value = client

            result = preflight_openwebui_delivery(
                config={
                    "cron": {
                        "openwebui": {
                            "base_url": "https://open-webui.example.com/",
                            "api_key": "test-key",
                            "timeout_seconds": 15,
                        }
                    }
                }
            )

        assert result == {
            "target": "openwebui",
            "base_url": "https://open-webui.example.com",
            "version": "0.8.12",
            "chat_count": 2,
            "message": "Open WebUI API reachable and authenticated chat listing succeeded.",
        }
        assert client.request.call_args_list[0].args == ("GET", "https://open-webui.example.com/api/version")
        assert client.request.call_args_list[1].args == ("GET", "https://open-webui.example.com/api/v1/chats/")
        headers = client_cls.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test-key"
