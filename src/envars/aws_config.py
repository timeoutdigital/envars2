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


def _build_config() -> Config:
    """Builds the bounded AWS client config from the current ``ENVARS_AWS_*`` environment values.

    Bounded so a stalled endpoint fails in seconds, not minutes. botocore treats
    ``retries.max_attempts`` as the RETRY count, so ``max_attempts=2`` resolves to 3 total
    attempts (1 initial + 2 retries, i.e. ``total_max_attempts=3``); with ``read_timeout=5s``
    the worst case is ~17s, versus botocore's default of ``read_timeout(60) x legacy 5
    attempts = ~300s``. A fully-unreachable endpoint fails the whole resolve regardless, so we
    fail fast rather than wait it out.
    """
    return Config(
        connect_timeout=_int_env("ENVARS_AWS_CONNECT_TIMEOUT", 3),
        read_timeout=_int_env("ENVARS_AWS_READ_TIMEOUT", 5),
        retries={"max_attempts": _int_env("ENVARS_AWS_MAX_ATTEMPTS", 2), "mode": "standard"},
    )


# Built once, at import. envars is a short-lived CLI, so reading ENVARS_AWS_* here (from the
# already-populated process environment) is equivalent to reading them per client — set any
# overrides in the environment before invoking envars, not after import. Every client is built
# from this shared instance; call _build_config() directly only if you need a dynamic re-read.
AWS_CLIENT_CONFIG = _build_config()
