import base64
from unittest.mock import patch

import boto3
from botocore.stub import Stubber

from src.envars.aws_kms import AWSKMSAgent


def test_encrypt():
    """Tests the encrypt function using botocore.stub.Stubber."""
    kms_client = boto3.client("kms", region_name="us-east-1")
    with Stubber(kms_client) as stubber:
        # Expected parameters for the encrypt call
        expected_params = {
            "KeyId": "test_key",
            "Plaintext": b"test_data",
            "EncryptionContext": {"app": "test_app", "env": "dev", "loc": "test_loc"},
        }
        # The response to return when encrypt is called
        response = {"CiphertextBlob": b"encrypted_data"}
        stubber.add_response("encrypt", response, expected_params)

        # We need to patch boto3.client to return our stubbed client
        with patch("boto3.client", return_value=kms_client):
            agent = AWSKMSAgent(region_name="us-east-1")
            encrypted_data = agent.encrypt(
                data="test_data",
                key_id="test_key",
                encryption_context={"app": "test_app", "env": "dev", "loc": "test_loc"},
            )

            assert encrypted_data == base64.b64encode(b"encrypted_data").decode("utf-8")
            stubber.assert_no_pending_responses()


def test_decrypt():
    """Tests the decrypt function using botocore.stub.Stubber."""
    kms_client = boto3.client("kms", region_name="us-east-1")
    with Stubber(kms_client) as stubber:
        # Expected parameters for the decrypt call
        expected_params = {
            "CiphertextBlob": b"encrypted_data",
            "EncryptionContext": {"app": "test_app", "env": "dev", "loc": "test_loc"},
        }
        # The response to return when decrypt is called
        response = {"Plaintext": b"decrypted_data"}
        stubber.add_response("decrypt", response, expected_params)

        # We need to patch boto3.client to return our stubbed client
        with patch("boto3.client", return_value=kms_client):
            agent = AWSKMSAgent(region_name="us-east-1")
            decrypted_data = agent.decrypt(
                encrypted_data=base64.b64encode(b"encrypted_data").decode("utf-8"),
                encryption_context={"app": "test_app", "env": "dev", "loc": "test_loc"},
            )

            assert decrypted_data == "decrypted_data"
            stubber.assert_no_pending_responses()
