import re
from importlib.metadata import version

import strapi_sync_hub


def test_version_is_semver_and_matches_package_metadata() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", strapi_sync_hub.__version__)
    assert strapi_sync_hub.__version__ == version("strapi-sync-hub")
