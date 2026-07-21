"""Tests for the shared bounded AWS client configuration (TOPS-2500)."""

from unittest.mock import MagicMock, patch

import boto3
from botocore.exceptions import ReadTimeoutError

from src.envars import aws_config, cloud_utils
from src.envars.aws_cloudformation import CloudFormationExports
from src.envars.aws_kms import AWSKMSAgent
from src.envars.aws_ssm import SSMParameterStore


def test_default_config_is_bounded():
    """The shared config caps timeouts and retries well below botocore's defaults (60s/60s/5)."""
    cfg = aws_config.AWS_CLIENT_CONFIG
    assert cfg.connect_timeout == 3
    assert cfg.read_timeout == 5
    assert cfg.retries == {"max_attempts": 2, "mode": "standard"}


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
