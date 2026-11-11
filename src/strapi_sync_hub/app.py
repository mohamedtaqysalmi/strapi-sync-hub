import hmac
import logging
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request

from strapi_sync_hub.dead_letter import DeadLetterLog
from strapi_sync_hub.errors import EventError, TargetError
from strapi_sync_hub.mapping import MappingConfig
from strapi_sync_hub.service import StrapiEvent, handle_event
from strapi_sync_hub.targets import Target

logger = logging.getLogger(__name__)


def create_app(
    *,
    secret: str,
    secret_header: str,
    mapping: MappingConfig,
    target: Target,
    dead_letter: DeadLetterLog | None = None,
) -> FastAPI:
    app = FastAPI(title="strapi-sync-hub")
    expected = secret.encode()

    def verify_secret(request: Request) -> None:
        provided = request.headers.get(secret_header)
        if provided is None:
            raise HTTPException(status_code=401, detail=f"missing {secret_header} header")
        if not hmac.compare_digest(provided.encode(), expected):
            raise HTTPException(status_code=403, detail=f"invalid {secret_header} header")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhook", dependencies=[Depends(verify_secret)])
    def webhook(event: StrapiEvent) -> dict[str, str]:
        try:
            result = handle_event(event, mapping, target)
        except EventError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except TargetError as exc:
            logger.error("target failed for %s on %s: %s", event.event, event.model, exc)
            if dead_letter is not None:
                dead_letter.record(
                    event=_event_payload(event),
                    error=str(exc),
                    detail=f"{event.event} {event.model}",
                )
                return {"status": "dead_lettered", "detail": str(exc)}
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        logger.info("%s %s: %s %s", event.event, event.model, result.status, result.detail)
        return {"status": result.status, "detail": result.detail}

    return app


def _event_payload(event: StrapiEvent) -> dict[str, Any]:
    return event.model_dump()
