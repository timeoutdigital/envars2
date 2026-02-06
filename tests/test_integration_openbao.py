import os
from unittest.mock import MagicMock, patch

from src.envars.main import Secret, _get_decrypted_value
from src.envars.models import VariableManager, VariableValue


@patch.dict(os.environ, {"VAULT_TOKEN": "test-token", "VAULT_ADDR": "http://localhost:8200"})
@patch("src.envars.main.OpenBaoKMSAgent")
def test_decryption_integration_openbao(mock_agent_class):
    """Test integration of OpenBao decryption in _get_decrypted_value."""
    mock_agent = MagicMock()
    mock_agent.decrypt.return_value = "decrypted-secret"
    mock_agent_class.return_value = mock_agent

    manager = VariableManager(app="test-app", kms_key="openbao:my-key")
    # cloud_provider is usually set during load_from_yaml or main callback
    manager.cloud_provider = "openbao"

    vv = VariableValue(
        variable_name="MY_SECRET", value=Secret("vault:v1:encrypted"), scope_type="ENVIRONMENT", environment_name="dev"
    )

    decrypted_value = _get_decrypted_value(manager, vv)

    assert decrypted_value == "decrypted-secret"
    mock_agent_class.assert_called_once_with(address="http://localhost:8200", token="test-token")  # noqa: S106
    mock_agent.decrypt.assert_called_once_with("vault:v1:encrypted", "my-key", {"app": "test-app", "env": "dev"})
