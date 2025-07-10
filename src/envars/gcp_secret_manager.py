import warnings

from google.cloud import secretmanager

warnings.filterwarnings("ignore", "Your application has authenticated using end user credentials")


class GCPSecretManager:
    def __init__(self):
        self.client = secretmanager.SecretManagerServiceClient()

    def access_secret_version(self, secret_version_name: str) -> str | None:
        try:
            response = self.client.access_secret_version(name=secret_version_name)
            return response.payload.data.decode("UTF-8")
        except Exception:
            return None
