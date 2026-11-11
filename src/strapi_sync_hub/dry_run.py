"""Target that records intended writes without calling a real backend."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from strapi_sync_hub.targets import Outcome

logger = logging.getLogger(__name__)


@dataclass
class PlannedAction:
    action: Literal["upsert", "delete"]
    index: str
    doc_id: str
    document: dict[str, Any] | None = None
    updated_at: datetime | None = None


@dataclass
class DryRunTarget:
    """Implements the Target protocol; never talks to Meilisearch or a webhook."""

    actions: list[PlannedAction] = field(default_factory=list)

    def upsert(
        self, index: str, doc_id: str, document: dict[str, Any], updated_at: datetime
    ) -> Outcome:
        planned = PlannedAction(
            action="upsert",
            index=index,
            doc_id=doc_id,
            document=dict(document),
            updated_at=updated_at,
        )
        self.actions.append(planned)
        logger.info("dry-run upsert %s/%s at %s", index, doc_id, updated_at.isoformat())
        return Outcome.APPLIED

    def delete(self, index: str, doc_id: str) -> Outcome:
        self.actions.append(PlannedAction(action="delete", index=index, doc_id=doc_id))
        logger.info("dry-run delete %s/%s", index, doc_id)
        return Outcome.APPLIED
