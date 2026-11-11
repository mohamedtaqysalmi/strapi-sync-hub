import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from strapi_sync_hub.app import create_app
from strapi_sync_hub.dead_letter import DeadLetterLog
from strapi_sync_hub.errors import TargetError
from strapi_sync_hub.mapping import MappingConfig
from strapi_sync_hub.targets import Outcome

SECRET = "a-secret-of-sufficient-length"
HEADER = "X-Sync-Secret"


class MemoryTarget:
    def __init__(self) -> None:
        self.docs: dict[tuple[str, str], dict[str, Any]] = {}
        self.fail = False

    def upsert(
        self, index: str, doc_id: str, document: dict[str, Any], updated_at: datetime
    ) -> Outcome:
        if self.fail:
            raise TargetError("down")
        self.docs[(index, doc_id)] = document
        return Outcome.APPLIED

    def delete(self, index: str, doc_id: str) -> Outcome:
        if self.fail:
            raise TargetError("down")
        self.docs.pop((index, doc_id), None)
        return Outcome.APPLIED


def test_dead_letter_appends_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "dlq.jsonl"
    log = DeadLetterLog(path)
    log.record(event={"event": "entry.create"}, error="down", detail="article")
    log.record(event={"event": "entry.delete"}, error="down again")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["error"] == "down"
    assert first["event"]["event"] == "entry.create"
    assert "recorded_at" in first


def test_webhook_dead_letters_after_target_failure(
    tmp_path: Path, mapping: MappingConfig, events: dict[str, dict[str, Any]]
) -> None:
    target = MemoryTarget()
    target.fail = True
    path = tmp_path / "dead-letter.jsonl"
    app = create_app(
        secret=SECRET,
        secret_header=HEADER,
        mapping=mapping,
        target=target,
        dead_letter=DeadLetterLog(path),
    )
    response = TestClient(app).post(
        "/webhook", json=events["entry.create"], headers={HEADER: SECRET}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "dead_lettered"
    recorded = json.loads(path.read_text(encoding="utf-8").strip())
    assert recorded["event"]["model"] == "article"
    assert "down" in recorded["error"]


def test_without_dead_letter_target_failure_is_502(
    mapping: MappingConfig, events: dict[str, dict[str, Any]]
) -> None:
    class Boom:
        def upsert(self, *args: object, **kwargs: object) -> Outcome:
            raise TargetError("down")

        def delete(self, *args: object, **kwargs: object) -> Outcome:
            raise TargetError("down")

    app = create_app(
        secret=SECRET, secret_header=HEADER, mapping=mapping, target=Boom(), dead_letter=None
    )
    response = TestClient(app).post(
        "/webhook", json=events["entry.create"], headers={HEADER: SECRET}
    )
    assert response.status_code == 502
