import boto3


class CloudFormationExports:
    def __init__(self, region_name: str | None = None):
        self.client = boto3.client("cloudformation", region_name=region_name)
        self._exports_cache: dict[str, str] | None = None

    def _populate_exports_cache(self):
        self._exports_cache = {}
        try:
            paginator = self.client.get_paginator("list_exports")
            for page in paginator.paginate():
                for export in page["Exports"]:
                    self._exports_cache[export["Name"]] = export["Value"]
        except Exception:
            self._exports_cache = None  # Invalidate cache on error

    def get_export_value(self, export_name: str) -> str | None:
        if self._exports_cache is None:
            self._populate_exports_cache()

        if self._exports_cache is not None:
            return self._exports_cache.get(export_name)

        return None
