"""Tests for the shared bounded AWS client configuration (TOPS-2500)."""

from unittest.mock import MagicMock, patch

import boto3
from botocore.exceptions import ReadTimeoutError

from src.envars import aws_config, cloud_utils
from src.envars.aws_cloudformation import CloudFormationExports
from src.envars.aws_kms import AWSKMSAgent
from src.envars.aws_ssm import SSMParameterStore


def test_default_config_is_bounded():
    """The shared config caps timeouts and retries well below botocore's defaults (60s/60s/5).

    Asserts individual keys rather than full-dict equality on ``retries``: botocore rewrites
    that dict in place when a client is built from the config (``max_attempts`` becomes
    ``total_max_attempts``), so an equality assertion would be order- and version-fragile.
    """
    cfg = aws_config.AWS_CLIENT_CONFIG
    assert cfg.connect_timeout == 3
    assert cfg.read_timeout == 5
    assert cfg.retries["mode"] == "standard"


def test_default_makes_three_total_attempts():
    """max_attempts=2 resolves to 3 total HTTP attempts (1 initial + 2 retries).

    botocore treats retries.max_attempts as the retry count, so total_max_attempts = N + 1
    (verified against botocore 1.39.4). Pinning the resolved value keeps the ~300s -> ~17s
    worst case from silently regressing if that mapping ever changes, and makes the PR's
    "3 total attempts" claim executable. Built from a fresh _build_config() so botocore's
    in-place rewrite of retries doesn't leak into the shared AWS_CLIENT_CONFIG other tests read.
    """
    client = boto3.client("sts", region_name="eu-west-1", config=aws_config._build_config())
    assert client.meta.config.retries["total_max_attempts"] == 3


def test_env_overrides_flow_through(monkeypatch):
    """All three ENVARS_AWS_* overrides wire through to the built config, not just read_timeout."""
    monkeypatch.setenv("ENVARS_AWS_CONNECT_TIMEOUT", "7")
    monkeypatch.setenv("ENVARS_AWS_READ_TIMEOUT", "11")
    monkeypatch.setenv("ENVARS_AWS_MAX_ATTEMPTS", "4")
    client = boto3.client("sts", region_name="eu-west-1", config=aws_config._build_config())
    assert client.meta.config.connect_timeout == 7
    assert client.meta.config.read_timeout == 11
    assert client.meta.config.retries["total_max_attempts"] == 5  # input 4 -> 5 total (N+1)


def test_int_env_parses_positive_override(monkeypatch):
    """_int_env returns a valid positive override from the environment."""
    monkeypatch.setenv("ENVARS_AWS_READ_TIMEOUT", "42")
    assert aws_config._int_env("ENVARS_AWS_READ_TIMEOUT", 10) == 42


def test_int_env_falls_back_when_unset_invalid_or_non_positive(monkeypatch):
    """Unset, non-numeric, and zero/negative values all fall back to the default."""
    monkeypatch.delenv("ENVARS_AWS_READ_TIMEOUT", raising=False)
    assert aws_config._int_env("ENVARS_AWS_READ_TIMEOUT", 10) == 10  # unset

    monkeypatch.setenv("ENVARS_AWS_READ_TIMEOUT", "not-an-int")
    assert aws_config._int_env("ENVARS_AWS_READ_TIMEOUT", 10) == 10  # invalid

    monkeypatch.setenv("ENVARS_AWS_READ_TIMEOUT", "0")
    assert aws_config._int_env("ENVARS_AWS_READ_TIMEOUT", 10) == 10  # non-positive


def test_kms_client_uses_bounded_config():
    """AWSKMSAgent constructs its client with the shared bounded config."""
    agent = AWSKMSAgent(region_name="eu-west-1")
    assert agent.kms_client.meta.config.connect_timeout == 3
    assert agent.kms_client.meta.config.read_timeout == 5


def test_ssm_client_uses_bounded_config():
    """SSMParameterStore constructs its client with the shared bounded config."""
    store = SSMParameterStore(region_name="eu-west-1")
    assert store.client.meta.config.read_timeout == 5


def test_cloudformation_client_uses_bounded_config():
    """CloudFormationExports constructs its client with the shared bounded config."""
    exports = CloudFormationExports(region_name="eu-west-1")
    assert exports.client.meta.config.read_timeout == 5


def test_get_aws_account_id_returns_none_on_timeout():
    """A stalled STS endpoint degrades to None instead of raising ReadTimeoutError.

    Regression for the DSS-3428 crash: get_aws_account_id only caught NoCredentialsError,
    so a stalled endpoint surfaced as an uncaught traceback out of `envars exec`.
    """
    stalled = MagicMock()
    stalled.get_caller_identity.side_effect = ReadTimeoutError(endpoint_url="https://sts.eu-west-1.amazonaws.com/")
    with patch.object(boto3, "client", return_value=stalled):
        assert cloud_utils.get_aws_account_id() is None
