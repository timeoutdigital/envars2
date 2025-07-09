import base64
import json

from google.cloud import kms_v1


class GCPKMSAgent:
    """A class to handle Google Cloud KMS operations."""

    def __init__(self):
        """Initializes the KMS client."""
        self.kms_client = kms_v1.KeyManagementServiceClient()

    def encrypt(self, data: str, key_path: str, encryption_context: dict[str, str]) -> str:
        """Encrypts data using the specified KMS key."""
        additional_authenticated_data = json.dumps(
            encryption_context,
            sort_keys=True,
        ).encode("utf-8")
        try:
            response = self.kms_client.encrypt(
                request={
                    "name": key_path,
                    "plaintext": data.encode("utf-8"),
                    "additional_authenticated_data": additional_authenticated_data,
                }
            )
            return base64.b64encode(response.ciphertext).decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"Failed to encrypt data with KMS key {key_path}: {e}") from e

    def decrypt(self, encrypted_data: str, key_path: str, encryption_context: dict[str, str]) -> str:
        """Decrypts data using the specified KMS key."""
        additional_authenticated_data = json.dumps(
            encryption_context,
            sort_keys=True,
        ).encode("utf-8")
        try:
            decoded_data = base64.b64decode(encrypted_data)
            response = self.kms_client.decrypt(
                request={
                    "name": key_path,
                    "ciphertext": decoded_data,
                    "additional_authenticated_data": additional_authenticated_data,
                }
            )
            return response.plaintext.decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"Failed to decrypt data with KMS key {key_path}: {e}") from e
