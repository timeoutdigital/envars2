import base64
import json

import requests


class OpenBaoKMSAgent:
    """A class to handle Openbao KMS operations."""

    def __init__(self, address: str, token: str, transit_mount: str = "transit"):
        """Initializes the Openbao client."""
        self.address = address.rstrip("/")
        self.token = token
        self.transit_mount = transit_mount
        self.headers = {"X-Vault-Token": self.token}

    def encrypt(self, data: str, key_id: str, encryption_context: dict[str, str]) -> str:
        """Encrypts data using the specified Openbao transit key."""
        # Openbao Transit Engine doesn't support additional_authenticated_data in the same way as AWS/GCP
        # but we can pass context if the key is derived. However, for simplicity and compatibility
        # we'll just encrypt the plaintext for now.
        # Most transit keys are not convergent/derived by default.

        plaintext_b64 = base64.b64encode(data.encode("utf-8")).decode("utf-8")
        url = f"{self.address}/v1/{self.transit_mount}/encrypt/{key_id}"
        payload = {"plaintext": plaintext_b64}

        if encryption_context:
            # Openbao transit engine can use context for key derivation if enabled on the key
            # We'll include it as 'context' just in case.
            context_b64 = base64.b64encode(json.dumps(encryption_context, sort_keys=True).encode("utf-8")).decode(
                "utf-8"
            )
            payload["context"] = context_b64

        response = requests.post(url, headers=self.headers, json=payload, timeout=10)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to encrypt data with Openbao: {response.text}")

        return response.json()["data"]["ciphertext"]

    def decrypt(self, encrypted_data: str, key_id: str, encryption_context: dict[str, str]) -> str:
        """Decrypts data using the specified Openbao transit key."""
        url = f"{self.address}/v1/{self.transit_mount}/decrypt/{key_id}"
        payload = {"ciphertext": encrypted_data}

        if encryption_context:
            context_b64 = base64.b64encode(json.dumps(encryption_context, sort_keys=True).encode("utf-8")).decode(
                "utf-8"
            )
            payload["context"] = context_b64

        response = requests.post(url, headers=self.headers, json=payload, timeout=10)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to decrypt data with Openbao: {response.text}")

        plaintext_b64 = response.json()["data"]["plaintext"]
        return base64.b64decode(plaintext_b64).decode("utf-8")
