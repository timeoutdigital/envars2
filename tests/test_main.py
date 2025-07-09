import pytest
import yaml

from src.envars.main import DuplicateKeyError, SafeLoaderWithDuplicatesCheck, load_from_yaml
from src.envars.models import VariableManager


# Helper function to create a temporary YAML file
def create_yaml_file(tmp_path, content):
    file_path = tmp_path / "test_config.yml"
    file_path.write_text(content)
    return str(file_path)


# Test cases for load_from_yaml
def test_load_from_yaml_full_config(tmp_path):
    yaml_content = """
configuration:
  environments:
    - dev
    - prod
  accounts:
    - aws_us_east: "12345"
    - gcp_us_central: "67890"

environment_variables:
  API_KEY:
    description: "API Key for external service"
    default: "default_api_key"
    dev: "dev_api_key"
    prod:
      aws_us_east: "prod_aws_api_key"
  DB_URL:
    description: "Database connection string"
    prod: "prod_db_url"
    gcp_us_central:
      dev: "dev_gcp_db_url"
  TEST_VAR:
    default: "test_default"
    dev: "test_dev"
    prod: "test_prod"
    aws_us_east: "test_aws"
    gcp_us_central: "test_gcp"
"""
    file_path = create_yaml_file(tmp_path, yaml_content)
    manager = load_from_yaml(file_path)

    assert isinstance(manager, VariableManager)
    assert "dev" in manager.environments
    assert "prod" in manager.environments
    assert any(loc.name == "aws_us_east" and loc.location_id == "12345" for loc in manager.locations.values())
    assert any(loc.name == "gcp_us_central" and loc.location_id == "67890" for loc in manager.locations.values())

    assert "API_KEY" in manager.variables
    assert "DB_URL" in manager.variables
    assert "TEST_VAR" in manager.variables

    # Test API_KEY values
    assert manager.get_variable_value("API_KEY", None, None) == "default_api_key"
    assert manager.get_variable_value("API_KEY", "dev", None) == "dev_api_key"
    assert manager.get_variable_value("API_KEY", "prod", "aws_us_east") == "prod_aws_api_key"
    assert manager.get_variable_value("API_KEY", "prod", "gcp_us_central") == "default_api_key"  # Falls back to default

    # Test DB_URL values
    assert manager.get_variable_value("DB_URL", "prod", None) == "prod_db_url"
    assert manager.get_variable_value("DB_URL", "dev", "gcp_us_central") == "dev_gcp_db_url"
    assert manager.get_variable_value("DB_URL", "prod", "aws_us_east") == "prod_db_url"  # Falls back to env specific

    # Test TEST_VAR values
    assert manager.get_variable_value("TEST_VAR", None, None) == "test_default"
    assert manager.get_variable_value("TEST_VAR", "dev", None) == "test_dev"
    assert manager.get_variable_value("TEST_VAR", "prod", None) == "test_prod"
    assert manager.get_variable_value("TEST_VAR", None, "aws_us_east") == "test_aws"
    assert manager.get_variable_value("TEST_VAR", None, "gcp_us_central") == "test_gcp"
    assert (
        manager.get_variable_value("TEST_VAR", "dev", "aws_us_east") == "test_dev"
    )  # Env takes precedence over location
    assert (
        manager.get_variable_value("TEST_VAR", "prod", "gcp_us_central") == "test_prod"
    )  # Env takes precedence over location


def test_load_from_yaml_empty_config(tmp_path):
    yaml_content = """
"""
    file_path = create_yaml_file(tmp_path, yaml_content)
    manager = load_from_yaml(file_path)
    assert isinstance(manager, VariableManager)
    assert not manager.environments
    assert not manager.locations
    assert not manager.variables
    assert not manager.variable_values


def test_load_from_yaml_missing_sections(tmp_path):
    yaml_content = """
environment_variables:
  VAR1:
    default: "value1"
"""
    file_path = create_yaml_file(tmp_path, yaml_content)
    manager = load_from_yaml(file_path)
    assert isinstance(manager, VariableManager)
    assert not manager.environments
    assert not manager.locations
    assert "VAR1" in manager.variables
    assert manager.get_variable_value("VAR1", None, None) == "value1"


# Test cases for DuplicateKeyError and SafeLoaderWithDuplicatesCheck
def test_duplicate_key_error_raised(tmp_path):
    yaml_content = """
key1: value1
key1: value2
"""
    file_path = create_yaml_file(tmp_path, yaml_content)
    with pytest.raises(DuplicateKeyError, match="Duplicate key: key1"):
        with open(file_path) as f:
            yaml.load(f, Loader=SafeLoaderWithDuplicatesCheck)


def test_duplicate_key_error_nested(tmp_path):
    yaml_content = """
parent:
  child1: value1
  child1: value2
"""
    file_path = create_yaml_file(tmp_path, yaml_content)
    with pytest.raises(DuplicateKeyError, match="Duplicate key: child1"):
        with open(file_path) as f:
            yaml.load(f, Loader=SafeLoaderWithDuplicatesCheck)


def test_safe_loader_no_duplicates(tmp_path):
    yaml_content = """
key1: value1
key2: value2
"""
    file_path = create_yaml_file(tmp_path, yaml_content)
    with open(file_path) as f:
        data = yaml.load(f, Loader=SafeLoaderWithDuplicatesCheck)
    assert data == {"key1": "value1", "key2": "value2"}
