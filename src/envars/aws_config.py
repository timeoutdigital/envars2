"""Shared botocore client configuration for envars' AWS calls.

Without an explicit ``Config``, ``boto3.client(...)`` inherits the botocore defaults:
``connect_timeout=60s``, ``read_timeout=60s`` and legacy retries (up to 5 attempts).
A single stalled STS/KMS/SSM/CloudFormation endpoint can therefore hang for up to
``5 x 60 = ~300s``, and a full resolve makes several such calls (STS for location
auto-detect, one KMS decrypt per secret, plus any ``parameter_store:`` /
``cloudformation_export:`` lookups). These bounds turn a silent multi-minute hang into
a fast, legible failure while still tolerating a transient blip.

Override per-environment via the ``ENVARS_AWS_*`` variables if the defaults are too tight.
"""

import os

from botocore.config import Config


def _int_env(name: str, default: int) -> int:
    """Reads a positive int from the environment, falling back to ``default``."""
    try:
        value = int(os.environ[name])
    except (KeyError, ValueError):
        return default
    return value if value > 0 else default


# Bounded so a stalled endpoint fails in seconds, not minutes. Standard retry mode adds
# one backoff retry for transient errors while capping the worst case far below botocore's
# default of read_timeout(60) x legacy 5 attempts = ~300s. A fully-unreachable endpoint
# means the whole resolve will fail regardless, so we fail fast rather than wait it out.
AWS_CLIENT_CONFIG = Config(
    connect_timeout=_int_env("ENVARS_AWS_CONNECT_TIMEOUT", 3),
    read_timeout=_int_env("ENVARS_AWS_READ_TIMEOUT", 5),
    retries={"max_attempts": _int_env("ENVARS_AWS_MAX_ATTEMPTS", 2), "mode": "standard"},
)
