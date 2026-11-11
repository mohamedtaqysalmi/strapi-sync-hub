class ConfigError(Exception):
    """Environment configuration is missing or invalid."""


class MappingError(Exception):
    """The YAML mapping file is invalid."""


class EventError(Exception):
    """A webhook event cannot be turned into a document."""


class TargetError(Exception):
    """A sync target rejected a request or could not be reached."""
