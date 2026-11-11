import copy
import json
from pathlib import Path
from typing import Any

import pytest

from strapi_sync_hub.mapping import MappingConfig, parse_mapping

FIXTURE = Path(__file__).parent / "fixtures" / "handwritten_from_docs_strapi_events.json"


@pytest.fixture
def events() -> dict[str, dict[str, Any]]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return copy.deepcopy(data["events"])


@pytest.fixture
def mapping() -> MappingConfig:
    return parse_mapping(
        {
            "content_types": {
                "article": {
                    "index": "articles",
                    "id_field": "documentId",
                    "fields": {"title": "title", "slug": "slug", "body": "content"},
                }
            }
        }
    )
