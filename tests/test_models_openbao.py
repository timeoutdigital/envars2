from src.envars.models import VariableManager


def test_variable_manager_openbao_string_config():
    """Test initializing VariableManager with OpenBao kms_key string."""
    kms_key = "openbao:my-key"
    manager = VariableManager(kms_key=kms_key)
    assert manager.cloud_provider == "openbao"
    assert manager.kms_key == kms_key
