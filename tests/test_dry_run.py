from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from strapi_sync_hub.app import create_app
from strapi_sync_hub.dry_run import DryRunTarget
from strapi_sync_hub.mapping import MappingConfig
from strapi_sync_hub.targets import Outcome

SECRET = "a-secret-of-sufficient-length"
HEADER = "X-Sync-Secret"
T1 = datetime(2025, 3, 1, 9, 0, tzinfo=UTC)


def test_dry_run_target_records_actions_without_side_effects() -> None:
    target = DryRunTarget()
    assert target.upsert("articles", "a1", {"title": "T"}, T1) is Outcome.APPLIED
    assert target.delete("articles", "a1") is Outcome.APPLIED
    assert [(a.action, a.index, a.doc_id) for a in target.actions] == [
        ("upsert", "articles", "a1"),
        ("delete", "articles", "a1"),
    ]


def test_webhook_dry_run_applies_without_real_target(
    mapping: MappingConfig, events: dict[str, dict[str, Any]]
) -> None:
    target = DryRunTarget()
    client = TestClient(
        create_app(secret=SECRET, secret_header=HEADER, mapping=mapping, target=target)
    )
    response = client.post("/webhook", json=events["entry.create"], headers={HEADER: SECRET})
    assert response.status_code == 200
    assert response.json()["status"] == "applied"
    assert target.actions[0].doc_id == "k3x9p0zq1v7w2m4n5b6c8d9e"
