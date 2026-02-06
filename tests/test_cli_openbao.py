import os
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.envars.cli import app
from src.envars.models import Environment, VariableManager

runner = CliRunner()


def test_cli_add_openbao_secret_no_token():
    """Test 'add' command with Openbao secret without token (proxy setup)."""
    manager = VariableManager(app="test-app", kms_key="openbao:my-key")
    manager.add_environment(Environment(name="dev"))

    with (
        patch("src.envars.cli.load_from_yaml", return_value=manager),
        patch("src.envars.openbao_kms.OpenBaoKMSAgent") as mock_agent_class,
        patch("src.envars.cli.write_envars_yml"),
        patch.dict(os.environ, {}, clear=True),
    ):
        mock_agent = MagicMock()
        mock_agent.encrypt.return_value = "vault:v1:encrypted-val"
        mock_agent_class.return_value = mock_agent

        # By default CliRunner captures both stdout and stderr in .output
        result = runner.invoke(app, ["add", "-s", "MY_SECRET=my-value", "-e", "dev"])

        assert result.exit_code == 0
        assert "Successfully added/updated MY_SECRET" in result.output
        mock_agent_class.assert_called_once_with(address="http://localhost:8200", token=None)
        mock_agent.encrypt.assert_called_once()


def test_cli_add_openbao_incompatible_prefix():
    """Test 'add' command blocks cloud prefixes when using Openbao."""
    manager = VariableManager(app="test-app", kms_key="openbao:my-key")
    manager.cloud_provider = "openbao"

    with patch("src.envars.cli.load_from_yaml", return_value=manager):
        result = runner.invoke(app, ["add", "MY_VAR=parameter_store:some-param"])

        assert result.exit_code == 1
        assert "Cannot use cloud-specific remote prefixes with an Openbao KMS key" in result.output
