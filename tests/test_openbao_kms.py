import base64
from unittest.mock import MagicMock, patch

from src.envars.openbao_kms import OpenBaoKMSAgent


def test_init():
    """Test that the OpenBaoKMSAgent can be initialized."""
    agent = OpenBaoKMSAgent(address="http://localhost:8200", token="test-token")  # noqa: S106
    assert agent.address == "http://localhost:8200"
    assert agent.token == "test-token"  # noqa: S105
    assert agent.headers["X-Vault-Token"] == "test-token"  # noqa: S105


def test_init_no_token():
    """Test initialization without a token."""
    agent = OpenBaoKMSAgent(address="http://localhost:8200")
    assert agent.token is None
    assert "X-Vault-Token" not in agent.headers


@patch("requests.post")
def test_encrypt(mock_post):
    """Test the encrypt method."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"ciphertext": "vault:v1:some-encrypted-data"}}
    mock_post.return_value = mock_response

    agent = OpenBaoKMSAgent(address="http://localhost:8200", token="test-token")  # noqa: S106
    encryption_context = {"app": "test-app"}
    ciphertext = agent.encrypt(data="my-secret", key_id="my-key", encryption_context=encryption_context)

    assert ciphertext == "vault:v1:some-encrypted-data"
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:8200/v1/transit/encrypt/my-key"
    assert kwargs["headers"]["X-Vault-Token"] == "test-token"
    assert "plaintext" in kwargs["json"]
    assert "context" in kwargs["json"]


@patch("requests.post")
def test_decrypt(mock_post):
    """Test the decrypt method."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"plaintext": base64.b64encode(b"my-secret").decode("utf-8")}}
    mock_post.return_value = mock_response

    agent = OpenBaoKMSAgent(address="http://localhost:8200", token="test-token")  # noqa: S106
    encryption_context = {"app": "test-app"}
    plaintext = agent.decrypt(
        encrypted_data="vault:v1:some-encrypted-data", key_id="my-key", encryption_context=encryption_context
    )

    assert plaintext == "my-secret"
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:8200/v1/transit/decrypt/my-key"
    assert kwargs["headers"]["X-Vault-Token"] == "test-token"
    assert kwargs["json"]["ciphertext"] == "vault:v1:some-encrypted-data"
    assert "context" in kwargs["json"]
