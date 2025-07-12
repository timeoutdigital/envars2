from unittest.mock import MagicMock, patch

import pytest

from src.envars.aws_cloudformation import CloudFormationExports


@pytest.fixture
def mock_boto3_client():
    """Fixture to mock the boto3 cloudformation client."""
    mock_client = MagicMock()
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {
            "Exports": [
                {"Name": "my-export-1", "Value": "value-1"},
                {"Name": "my-export-2", "Value": "value-2"},
            ]
        },
        {
            "Exports": [
                {"Name": "my-export-3", "Value": "value-3"},
            ]
        },
    ]
    mock_client.get_paginator.return_value = paginator
    return mock_client


def test_get_export_value_success(mock_boto3_client):
    """Test successfully retrieving a CloudFormation export value."""
    with patch("boto3.client", return_value=mock_boto3_client):
        cf_exports = CloudFormationExports()
        value = cf_exports.get_export_value("my-export-2")
        assert value == "value-2"
        # Verify that the paginator was called
        mock_boto3_client.get_paginator.assert_called_once_with("list_exports")
        mock_boto3_client.get_paginator.return_value.paginate.assert_called_once()


def test_get_export_value_not_found(mock_boto3_client):
    """Test that None is returned when an export is not found."""
    with patch("boto3.client", return_value=mock_boto3_client):
        cf_exports = CloudFormationExports()
        value = cf_exports.get_export_value("non-existent-export")
        assert value is None


def test_caching_logic(mock_boto3_client):
    """Test that the export values are cached after the first call."""
    with patch("boto3.client", return_value=mock_boto3_client):
        cf_exports = CloudFormationExports()

        # First call - should call the API
        value1 = cf_exports.get_export_value("my-export-1")
        assert value1 == "value-1"
        mock_boto3_client.get_paginator.return_value.paginate.assert_called_once()

        # Second call - should use the cache and not call the API again
        value2 = cf_exports.get_export_value("my-export-3")
        assert value2 == "value-3"
        mock_boto3_client.get_paginator.return_value.paginate.assert_called_once()  # Still called only once

        # Third call for a non-existent value
        value3 = cf_exports.get_export_value("non-existent")
        assert value3 is None
        mock_boto3_client.get_paginator.return_value.paginate.assert_called_once()  # Still called only once


def test_get_export_value_api_error(mock_boto3_client):
    """Test that None is returned when the AWS API call fails."""
    mock_boto3_client.get_paginator.side_effect = Exception("AWS API Error")
    with patch("boto3.client", return_value=mock_boto3_client):
        cf_exports = CloudFormationExports()
        value = cf_exports.get_export_value("my-export-1")
        assert value is None
        # Also test that the cache is invalidated
        assert cf_exports._exports_cache is None
