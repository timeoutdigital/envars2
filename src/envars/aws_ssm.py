import boto3


class SSMParameterStore:
    def __init__(self, region_name: str | None = None):
        self.client = boto3.client("ssm", region_name=region_name)

    def get_parameter(self, name: str, with_decryption: bool = True) -> str | None:
        try:
            response = self.client.get_parameter(Name=name, WithDecryption=with_decryption)
            return response["Parameter"]["Value"]
        except self.client.exceptions.ParameterNotFound:
            return None
