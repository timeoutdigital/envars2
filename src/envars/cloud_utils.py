import os
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from google.auth import default as google_auth_default
from google.auth.exceptions import DefaultCredentialsError

from .aws_config import AWS_CLIENT_CONFIG


def _debug(message):
    """Prints a debug message to stderr if ENVARS_DEBUG is set."""
    if os.environ.get("ENVARS_DEBUG"):
        print(f"DEBUG: {message}", file=sys.stderr)


def get_aws_account_id() -> str | None:
    """Retrieves the AWS account ID from the current credentials."""
    try:
        account_id = boto3.client("sts", config=AWS_CLIENT_CONFIG).get_caller_identity().get("Account")
        _debug(f"Found AWS Account ID: {account_id}")
        return account_id
    except (BotoCoreError, ClientError) as e:
        # NoCredentialsError, connect/read timeouts and API errors all land here. This is
        # best-effort location auto-detection, so degrade to "unknown" (the caller then asks
        # for --loc) instead of hanging/crashing when STS is slow or unreachable.
        _debug(f"Could not determine AWS account ID: {type(e).__name__}: {e}")
        return None


def get_gcp_project_id() -> str | None:
    """Retrieves the GCP project ID from the current credentials."""
    try:
        _, project_id = google_auth_default()
        if project_id:
            _debug(f"Found GCP Project ID: {project_id}")
            return project_id
        _debug("No GCP project found for the current credentials.")
        return None
    except DefaultCredentialsError:
        _debug("No GCP credentials found.")
        return None


def get_default_location_name(manager) -> str | None:
    """Determines the default location name based on the cloud provider."""
    _debug("Attempting to detect default location...")
    if manager.cloud_provider == "aws":
        _debug("Cloud provider is AWS.")
        account_id = get_aws_account_id()
        if account_id:
            for loc in manager.locations.values():
                _debug(f"Checking location: {loc.name} with ID: {loc.location_id}")
                if loc.location_id == account_id:
                    _debug(f"Default location found: {loc.name}")
                    return loc.name
    elif manager.cloud_provider == "gcp":
        _debug("Cloud provider is GCP.")
        project_id = get_gcp_project_id()
        if project_id:
            for loc in manager.locations.values():
                _debug(f"Checking location: {loc.name} with ID: {loc.location_id}")
                if loc.location_id == project_id:
                    _debug(f"Default location found: {loc.name}")
                    return loc.name
    _debug("No default location found.")
    return None
