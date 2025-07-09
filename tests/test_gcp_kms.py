import base64
import json
from unittest.mock import MagicMock

from src.envars.gcp_kms import GCPKMSAgent


def test_encrypt(monkeypatch):
    """Tests the encrypt function."""
    mock_kms_client = MagicMock()
    mock_kms_client.encrypt.return_value.ciphertext = b"encrypted_data"
    monkeypatch.setattr("google.cloud.kms_v1.KeyManagementServiceClient", lambda: mock_kms_client)

    agent = GCPKMSAgent()
    encrypted_data = agent.encrypt(
        data="test_data",
        key_path="test_key_path",
        encryption_context={"app": "test_app", "env": "dev", "loc": "test_loc"},
    )

    assert encrypted_data == base64.b64encode(b"encrypted_data").decode("utf-8")
    additional_authenticated_data = json.dumps(
        {"app": "test_app", "env": "dev", "loc": "test_loc"}, sort_keys=True
    ).encode("utf-8")
    mock_kms_client.encrypt.assert_called_once_with(
        request={
            "name": "test_key_path",
            "plaintext": b"test_data",
            "additional_authenticated_data": additional_authenticated_data,
        }
    )


def test_decrypt(monkeypatch):
    """Tests the decrypt function."""
    mock_kms_client = MagicMock()
    mock_kms_client.decrypt.return_value.plaintext = b"decrypted_data"
    monkeypatch.setattr("google.cloud.kms_v1.KeyManagementServiceClient", lambda: mock_kms_client)

    agent = GCPKMSAgent()
    decrypted_data = agent.decrypt(
        encrypted_data=base64.b64encode(b"encrypted_data").decode("utf-8"),
        key_path="test_key_path",
        encryption_context={"app": "test_app", "env": "dev", "loc": "test_loc"},
    )

    assert decrypted_data == "decrypted_data"
    additional_authenticated_data = json.dumps(
        {"app": "test_app", "env": "dev", "loc": "test_loc"}, sort_keys=True
    ).encode("utf-8")
    mock_kms_client.decrypt.assert_called_once_with(
        request={
            "name": "test_key_path",
            "ciphertext": b"encrypted_data",
            "additional_authenticated_data": additional_authenticated_data,
        }
    )
