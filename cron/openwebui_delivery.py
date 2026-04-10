"""Open WebUI delivery helpers for cron jobs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import uuid4

import httpx

from hermes_cli.config import load_config
from hermes_time import now as _hermes_now

DEFAULT_TITLE_TEMPLATE = "{job_name} – {date}"
DEFAULT_USER_MESSAGE_TEMPLATE = "Scheduled task result for {job_name} at {datetime}"
DEFAULT_MODEL_NAME = "hermes-agent"
DEFAULT_TIMEOUT_SECONDS = 30.0


class OpenWebUIDeliveryError(RuntimeError):
    """Raised when Open WebUI delivery cannot be completed."""


@dataclass(frozen=True)
class OpenWebUIDeliveryConfig:
    base_url: str
    api_key: str
    title_template: str = DEFAULT_TITLE_TEMPLATE
    user_message_template: str = DEFAULT_USER_MESSAGE_TEMPLATE
    model_name: str = DEFAULT_MODEL_NAME
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


def _new_id() -> str:
    return str(uuid4())


def _job_name(job: Dict[str, Any]) -> str:
    name = str(job.get("name") or "").strip()
    if name:
        return name
    job_id = str(job.get("id") or "").strip()
    return job_id or "Scheduled task"


def _job_schedule(job: Dict[str, Any]) -> str:
    schedule_display = str(job.get("schedule_display") or "").strip()
    if schedule_display:
        return schedule_display

    schedule = job.get("schedule")
    if isinstance(schedule, dict):
        rendered = str(schedule.get("display") or schedule.get("expr") or schedule.get("kind") or "").strip()
        if rendered:
            return rendered

    return ""


def _load_delivery_config(config: Optional[Dict[str, Any]] = None) -> OpenWebUIDeliveryConfig:
    loaded = config if config is not None else load_config()
    cron_cfg = loaded.get("cron", {}) if isinstance(loaded, dict) else {}
    owui_cfg = cron_cfg.get("openwebui", {}) if isinstance(cron_cfg, dict) else {}

    if not isinstance(owui_cfg, dict):
        owui_cfg = {}

    base_url = str(owui_cfg.get("base_url") or "").strip().rstrip("/")
    api_key = str(owui_cfg.get("api_key") or "").strip()
    title_template = str(owui_cfg.get("title_template") or DEFAULT_TITLE_TEMPLATE).strip()
    user_message_template = str(owui_cfg.get("user_message_template") or DEFAULT_USER_MESSAGE_TEMPLATE).strip()
    model_name = str(owui_cfg.get("model_name") or DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME
    timeout_seconds = float(owui_cfg.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)

    if not base_url:
        raise OpenWebUIDeliveryError("cron.openwebui.base_url is required for deliver='openwebui'")
    if not api_key:
        raise OpenWebUIDeliveryError("cron.openwebui.api_key is required for deliver='openwebui'")

    return OpenWebUIDeliveryConfig(
        base_url=base_url,
        api_key=api_key,
        title_template=title_template,
        user_message_template=user_message_template,
        model_name=model_name,
        timeout_seconds=max(1.0, timeout_seconds),
    )


def _render_template(template: str, *, job: Dict[str, Any], iso_datetime: str, date: str) -> str:
    template_values = {
        "date": date,
        "datetime": iso_datetime,
        "job_id": str(job.get("id") or "").strip(),
        "job_name": _job_name(job),
        "schedule": _job_schedule(job),
    }
    try:
        return template.format(**template_values)
    except KeyError as exc:
        missing = exc.args[0]
        available = ", ".join(sorted(template_values))
        raise OpenWebUIDeliveryError(
            f"Unknown placeholder '{{{missing}}}' in Open WebUI template. Available placeholders: {available}"
        ) from exc


def _request_json(client: httpx.Client, method: str, url: str, **kwargs: Any) -> Any:
    try:
        response = client.request(method, url, **kwargs)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        raise OpenWebUIDeliveryError(f"Open WebUI request failed for {url} (HTTP {status}): {exc}") from exc
    except httpx.HTTPError as exc:
        raise OpenWebUIDeliveryError(f"Open WebUI request failed for {url}: {exc}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise OpenWebUIDeliveryError(f"Open WebUI returned invalid JSON for {url}: {exc}") from exc


def _extract_chat_count(data: Any) -> Optional[int]:
    if isinstance(data, list):
        return len(data)

    if not isinstance(data, dict):
        return None

    for key in ("count", "total", "totalCount"):
        value = data.get(key)
        if isinstance(value, int):
            return value

    for key in ("chats", "items", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return len(value)

    return None


def _build_chat_payload(job: Dict[str, Any], content: str, delivery_config: OpenWebUIDeliveryConfig) -> Dict[str, Any]:
    now = _hermes_now()
    timestamp = int(now.timestamp())
    iso_datetime = now.isoformat()
    date_text = now.strftime("%Y-%m-%d")

    chat_id = _new_id()
    user_id = _new_id()
    assistant_id = _new_id()

    title = _render_template(delivery_config.title_template, job=job, iso_datetime=iso_datetime, date=date_text)
    user_content = _render_template(
        delivery_config.user_message_template,
        job=job,
        iso_datetime=iso_datetime,
        date=date_text,
    )

    user_message = {
        "id": user_id,
        "parentId": None,
        "childrenIds": [assistant_id],
        "role": "user",
        "content": user_content,
        "timestamp": timestamp,
        "models": [delivery_config.model_name],
    }
    assistant_message = {
        "id": assistant_id,
        "parentId": user_id,
        "childrenIds": [],
        "role": "assistant",
        "content": content,
        "timestamp": timestamp,
        "model": delivery_config.model_name,
        "modelName": delivery_config.model_name,
        "modelIdx": 0,
        "done": True,
    }
    chat = {
        "id": chat_id,
        "title": title,
        "models": [delivery_config.model_name],
        "params": {},
        "history": {
            "currentId": assistant_id,
            "messages": {
                user_id: user_message,
                assistant_id: assistant_message,
            },
        },
        "messages": [user_message, assistant_message],
        "tags": [],
        "timestamp": timestamp,
        "files": [],
        "system": None,
    }
    return {
        "title": title,
        "chat": chat,
    }


def deliver_to_openwebui(
    job: Dict[str, Any],
    content: str,
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a new Open WebUI chat containing a cron job result."""
    delivery_config = _load_delivery_config(config)
    payload = _build_chat_payload(job, content, delivery_config)

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {delivery_config.api_key}",
    }
    timeout = httpx.Timeout(delivery_config.timeout_seconds)
    url = f"{delivery_config.base_url}/api/v1/chats/new"

    with httpx.Client(timeout=timeout, headers=headers) as client:
        data = _request_json(client, "POST", url, json={"chat": payload["chat"]})

    created = data.get("chat") if isinstance(data, dict) else None
    created_row_id = data.get("id") if isinstance(data, dict) else None
    created_chat_id = created.get("id") if isinstance(created, dict) else None

    return {
        "chat_id": created_row_id or payload["chat"]["id"],
        "chat_payload_id": created_chat_id or payload["chat"]["id"],
        "title": payload["title"],
        "response": data,
    }


def preflight_openwebui_delivery(*, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate Open WebUI cron delivery config and authenticated API access."""
    delivery_config = _load_delivery_config(config)
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {delivery_config.api_key}",
    }
    timeout = httpx.Timeout(delivery_config.timeout_seconds)
    version_url = f"{delivery_config.base_url}/api/version"
    chats_url = f"{delivery_config.base_url}/api/v1/chats/"

    with httpx.Client(timeout=timeout, headers=headers) as client:
        version_data = _request_json(client, "GET", version_url)
        chats_data = _request_json(client, "GET", chats_url)

    version = version_data.get("version") if isinstance(version_data, dict) else None
    chat_count = _extract_chat_count(chats_data)

    return {
        "target": "openwebui",
        "base_url": delivery_config.base_url,
        "version": version,
        "chat_count": chat_count,
        "message": "Open WebUI API reachable and authenticated chat listing succeeded.",
    }
