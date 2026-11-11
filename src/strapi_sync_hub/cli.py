"""CLI: ``strapi-sync-hub reindex`` and ``strapi-sync-hub version``."""

from __future__ import annotations

import argparse
import logging
import sys

import httpx

from strapi_sync_hub import __version__
from strapi_sync_hub.config import Settings
from strapi_sync_hub.dry_run import DryRunTarget
from strapi_sync_hub.errors import ConfigError, EventError, MappingError, TargetError
from strapi_sync_hub.main import TIMEOUT_SECONDS, build_target
from strapi_sync_hub.mapping import load_mapping
from strapi_sync_hub.reindex import reindex

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("strapi_sync_hub.cli")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="strapi-sync-hub")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="Print the package version")

    reindex_parser = sub.add_parser(
        "reindex",
        help="Pull published entries from Strapi and upsert them into the configured target",
    )
    reindex_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan upserts without writing to Meilisearch or the webhook target",
    )
    reindex_parser.add_argument(
        "--content-type",
        action="append",
        dest="content_types",
        metavar="MODEL",
        help="Limit to one mapped model (repeatable). Default: every content type in the mapping.",
    )

    args = parser.parse_args(argv)
    if args.command == "version":
        print(__version__)
        return 0
    if args.command == "reindex":
        return _cmd_reindex(dry_run=args.dry_run, content_types=args.content_types)
    parser.error(f"unknown command {args.command}")
    return 2


def _cmd_reindex(*, dry_run: bool, content_types: list[str] | None) -> int:
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        logger.error("%s", exc)
        return 2
    if not settings.strapi_url:
        logger.error("STRAPI_URL is required for reindex")
        return 2
    try:
        mapping = load_mapping(settings.mapping_file)
    except MappingError as exc:
        logger.error("%s", exc)
        return 2

    target = DryRunTarget() if dry_run or settings.dry_run else build_target(settings)
    headers = (
        {"Authorization": f"Bearer {settings.strapi_api_token}"}
        if settings.strapi_api_token
        else {}
    )
    try:
        with httpx.Client(
            base_url=settings.strapi_url, headers=headers, timeout=TIMEOUT_SECONDS
        ) as client:
            summary = reindex(mapping, target, client, content_types=content_types)
    except (EventError, TargetError) as exc:
        logger.error("reindex aborted: %s", exc)
        return 1

    if isinstance(target, DryRunTarget):
        for action in target.actions:
            logger.info(
                "planned %s %s/%s",
                action.action,
                action.index,
                action.doc_id,
            )
    logger.info(
        "reindex done: scanned=%s applied=%s skipped=%s failed=%s",
        summary.scanned,
        summary.applied,
        summary.skipped,
        summary.failed,
    )
    return 1 if summary.failed else 0


if __name__ == "__main__":
    sys.exit(main())
