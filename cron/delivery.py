"""Cron delivery target helpers.

Separates exact delivery-target integrations (like Open WebUI) from the generic
message-gateway routing path used for origin/platform delivery.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

from cron.openwebui_delivery import deliver_to_openwebui, preflight_openwebui_delivery


DeliveryHandler = Callable[[dict, str], dict]
PreflightHandler = Callable[[], dict]


@dataclass(frozen=True)
class ExactDeliveryTarget:
    name: str
    handler: DeliveryHandler
    preflight: Optional[PreflightHandler] = None


_EXACT_DELIVERY_TARGETS: Dict[str, ExactDeliveryTarget] = {
    "openwebui": ExactDeliveryTarget(
        name="openwebui",
        handler=deliver_to_openwebui,
        preflight=preflight_openwebui_delivery,
    ),
}


def get_exact_delivery_target(deliver: Optional[str]) -> Optional[ExactDeliveryTarget]:
    if not deliver:
        return None
    return _EXACT_DELIVERY_TARGETS.get(str(deliver).strip().lower())
