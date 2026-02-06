from src.envars.openbao_kms import OpenBaoKMSAgent


def test_init():
    """Test that the OpenBaoKMSAgent can be initialized."""
    agent = OpenBaoKMSAgent(address="http://localhost:8200", token="test-token")  # noqa: S106
    assert agent is not None
