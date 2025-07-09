import base64
from unittest.mock import MagicMock

from src.envars.aws_kms import KMSAgent


def test_encrypt(monkeypatch):
    """Tests the encrypt function."""
    mock_kms_client = MagicMock()
    mock_kms_client.encrypt.return_value = {"CiphertextBlob": b"encrypted_data"}
    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: mock_kms_client)

    agent = KMSAgent(region_name="us-east-1")
    encrypted_data = agent.encrypt(
        data="test_data",
        key_id="test_key",
        encryption_context={"app": "test_app", "env": "dev", "loc": "test_loc"},
    )

    assert encrypted_data == base64.b64encode(b"encrypted_data").decode("utf-8")
    mock_kms_client.encrypt.assert_called_once_with(
        KeyId="test_key",
        Plaintext=b"test_data",
        EncryptionContext={"app": "test_app", "env": "dev", "loc": "test_loc"},
    )


def test_decrypt(monkeypatch):
    """Tests the decrypt function."""
    mock_kms_client = MagicMock()
    mock_kms_client.decrypt.return_value = {"Plaintext": b"decrypted_data"}
    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: mock_kms_client)

    agent = KMSAgent(region_name="us-east-1")
    decrypted_data = agent.decrypt(
        encrypted_data=base64.b64encode(b"encrypted_data").decode("utf-8"),
        encryption_context={"app": "test_app", "env": "dev", "loc": "test_loc"},
    )

    assert decrypted_data == "decrypted_data"
    mock_kms_client.decrypt.assert_called_once_with(
        CiphertextBlob=b"encrypted_data",
        EncryptionContext={"app": "test_app", "env": "dev", "loc": "test_loc"},
    )
