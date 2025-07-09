import base64

import boto3
from botocore.exceptions import ClientError


class AWSKMSAgent:
    """A class to handle AWS KMS operations."""

    def __init__(self, region_name: str | None = None):
        """Initializes the KMS client."""
        self.kms_client = boto3.client("kms", region_name=region_name)

    def encrypt(self, data: str, key_id: str, encryption_context: dict[str, str]) -> str:
        """Encrypts data using the specified KMS key."""
        try:
            response = self.kms_client.encrypt(
                KeyId=key_id,
                Plaintext=data.encode("utf-8"),
                EncryptionContext=encryption_context,
            )
            return base64.b64encode(response["CiphertextBlob"]).decode("utf-8")
        except ClientError as e:
            # Handle specific KMS errors if needed
            raise RuntimeError(f"Failed to encrypt data with KMS key {key_id}: {e}") from e

    def decrypt(self, encrypted_data: str, encryption_context: dict[str, str]) -> str:
        """Decrypts data using KMS."""
        try:
            decoded_data = base64.b64decode(encrypted_data)
            response = self.kms_client.decrypt(
                CiphertextBlob=decoded_data,
                EncryptionContext=encryption_context,
            )
            return response["Plaintext"].decode("utf-8")
        except ClientError as e:
            # Handle specific KMS errors if needed
            raise RuntimeError(f"Failed to decrypt data with KMS: {e}") from e
