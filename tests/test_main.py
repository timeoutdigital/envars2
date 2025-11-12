from unittest.mock import MagicMock

import pytest
import yaml

from src.envars.main import (
    DuplicateKeyError,
    SafeLoaderWithDuplicatesCheck,
    _get_resolved_variables,
    load_from_yaml,
    write_envars_yml,
)
from src.envars.models import Environment, Location, Variable, VariableManager, VariableValue


# Helper function to create a temporary YAML file
def create_yaml_file(tmp_path, content):
    file_path = tmp_path / "test_config.yml"
    file_path.write_text(content)
    return str(file_path)


def test_write_envars_yml_full_config(tmp_path):
    manager = VariableManager()

    # Add environments
    manager.add_environment(Environment(name="dev"))
    manager.add_environment(Environment(name="prod"))

    # Add locations
    aws_loc = Location(name="aws_us_east", location_id="12345")
    gcp_loc = Location(name="gcp_us_central", location_id="67890")
    manager.add_location(aws_loc)
    manager.add_location(gcp_loc)

    # Add variables
    manager.add_variable(Variable(name="API_KEY", description="API Key for external service"))
    manager.add_variable(Variable(name="DB_URL", description="Database connection string"))
    manager.add_variable(Variable(name="TEST_VAR"))

    # Add variable values
    manager.add_variable_value(VariableValue(variable_name="API_KEY", value="default_api_key", scope_type="DEFAULT"))
    manager.add_variable_value(
        VariableValue(variable_name="API_KEY", value="dev_api_key", scope_type="ENVIRONMENT", environment_name="dev")
    )
    manager.add_variable_value(
        VariableValue(
            variable_name="API_KEY",
            value="prod_aws_api_key",
            scope_type="SPECIFIC",
            environment_name="prod",
            location_id=aws_loc.location_id,
        )
    )

    manager.add_variable_value(
        VariableValue(variable_name="DB_URL", value="prod_db_url", scope_type="ENVIRONMENT", environment_name="prod")
    )
    manager.add_variable_value(
        VariableValue(
            variable_name="DB_URL",
            value="dev_gcp_db_url",
            scope_type="SPECIFIC",
            environment_name="dev",
            location_id=gcp_loc.location_id,
        )
    )

    manager.add_variable_value(VariableValue(variable_name="TEST_VAR", value="test_default", scope_type="DEFAULT"))
    manager.add_variable_value(
        VariableValue(variable_name="TEST_VAR", value="test_dev", scope_type="ENVIRONMENT", environment_name="dev")
    )
    manager.add_variable_value(
        VariableValue(variable_name="TEST_VAR", value="test_prod", scope_type="ENVIRONMENT", environment_name="prod")
    )
    manager.add_variable_value(
        VariableValue(
            variable_name="TEST_VAR", value="test_aws", scope_type="LOCATION", location_id=aws_loc.location_id
        )
    )
    manager.add_variable_value(
        VariableValue(
            variable_name="TEST_VAR", value="test_gcp", scope_type="LOCATION", location_id=gcp_loc.location_id
        )
    )

    output_file = tmp_path / "output.yml"
    write_envars_yml(manager, str(output_file))

    with open(output_file) as f:
        generated_yaml = f.read()

    expected_yaml = """
configuration:
  app: null
  kms_key: null
  description_mandatory: false
  environments:
  - dev
  - prod
  locations:
  - aws_us_east: '12345'
  - gcp_us_central: '67890'

environment_variables:
  API_KEY:
    description: API Key for external service
    default: default_api_key
    dev: dev_api_key
    prod:
      aws_us_east: prod_aws_api_key

  DB_URL:
    description: Database connection string
    prod: prod_db_url
    dev:
      gcp_us_central: dev_gcp_db_url

  TEST_VAR:
    default: test_default
    dev: test_dev
    prod: test_prod
    aws_us_east: test_aws
    gcp_us_central: test_gcp
"""
    assert generated_yaml.strip() == expected_yaml.strip()

    # Round-trip test: load the generated YAML and compare managers
    loaded_manager = load_from_yaml(str(output_file))

    assert len(loaded_manager.environments) == len(manager.environments)
    assert all(env in loaded_manager.environments for env in manager.environments)

    assert len(loaded_manager.locations) == len(manager.locations)
    assert all(loc.name in [l.name for l in loaded_manager.locations.values()] for loc in manager.locations.values())

    assert len(loaded_manager.variables) == len(manager.variables)
    assert all(var in loaded_manager.variables for var in manager.variables)

    # Compare variable values by iterating through all possible combinations
    for var_name in manager.variables:
        for env_name in list(manager.environments.keys()) + [None]:
            for loc_name in [loc.name for loc in manager.locations.values()] + [None]:
                expected_var = manager.get_variable(var_name, env_name, loc_name)
                actual_var = loaded_manager.get_variable(var_name, env_name, loc_name)
                expected_value = expected_var.value if expected_var else None
                actual_value = actual_var.value if actual_var else None
                assert expected_value == actual_value


def test_load_from_yaml_with_kms_key(tmp_path):
    yaml_content = """
configuration:
  kms_key: "global-kms-key"
  environments:
    - prod
  locations:
    - aws:
        id: "12345"
        kms_key: "aws-kms-key"
"""
    file_path = create_yaml_file(tmp_path, yaml_content)
    manager = load_from_yaml(file_path)
    assert manager.kms_key == "global-kms-key"
    aws_loc = next(loc for loc in manager.locations.values() if loc.name == "aws")
    assert aws_loc.kms_key == "aws-kms-key"


# Test cases for load_from_yaml
def test_load_from_yaml_full_config(tmp_path):
    yaml_content = """
configuration:
  environments:
    - dev
    - prod
  locations:
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
    api_key_default = manager.get_variable("API_KEY", None, None)
    assert api_key_default and api_key_default.value == "default_api_key"
    api_key_dev = manager.get_variable("API_KEY", "dev", None)
    assert api_key_dev and api_key_dev.value == "dev_api_key"
    api_key_prod_aws = manager.get_variable("API_KEY", "prod", "aws_us_east")
    assert api_key_prod_aws and api_key_prod_aws.value == "prod_aws_api_key"
    api_key_prod_gcp = manager.get_variable("API_KEY", "prod", "gcp_us_central")
    assert api_key_prod_gcp and api_key_prod_gcp.value == "default_api_key"  # Falls back to default

    # Test DB_URL values
    db_url_prod = manager.get_variable("DB_URL", "prod", None)
    assert db_url_prod and db_url_prod.value == "prod_db_url"
    db_url_dev_gcp = manager.get_variable("DB_URL", "dev", "gcp_us_central")
    assert db_url_dev_gcp and db_url_dev_gcp.value == "dev_gcp_db_url"
    db_url_prod_aws = manager.get_variable("DB_URL", "prod", "aws_us_east")
    assert db_url_prod_aws and db_url_prod_aws.value == "prod_db_url"  # Falls back to env specific

    # Test TEST_VAR values
    test_var_default = manager.get_variable("TEST_VAR", None, None)
    assert test_var_default and test_var_default.value == "test_default"
    test_var_dev = manager.get_variable("TEST_VAR", "dev", None)
    assert test_var_dev and test_var_dev.value == "test_dev"
    test_var_prod = manager.get_variable("TEST_VAR", "prod", None)
    assert test_var_prod and test_var_prod.value == "test_prod"
    test_var_aws = manager.get_variable("TEST_VAR", None, "aws_us_east")
    assert test_var_aws and test_var_aws.value == "test_aws"
    test_var_gcp = manager.get_variable("TEST_VAR", None, "gcp_us_central")
    assert test_var_gcp and test_var_gcp.value == "test_gcp"
    test_var_dev_aws = manager.get_variable("TEST_VAR", "dev", "aws_us_east")
    assert test_var_dev_aws and test_var_dev_aws.value == "test_dev"  # Env takes precedence over location
    test_var_prod_gcp = manager.get_variable("TEST_VAR", "prod", "gcp_us_central")
    assert test_var_prod_gcp and test_var_prod_gcp.value == "test_prod"  # Env takes precedence over location


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
    var1 = manager.get_variable("VAR1", None, None)
    assert var1 and var1.value == "value1"


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


def test_get_env_without_locations_and_no_loc_arg(tmp_path):
    """Test that get_env works correctly when no locations are configured and no --loc is provided."""
    yaml_content = """
configuration:
  environments:
    - dev

environment_variables:
  MY_VAR:
    default: "default_value"
  ANOTHER_VAR:
    dev: "dev_value"
"""
    file_path = create_yaml_file(tmp_path, yaml_content)
    manager = load_from_yaml(file_path)
    assert not manager.locations  # Ensure no locations are loaded

    # Test get_env
    from src.envars.main import get_env

    resolved_vars = get_env(env="dev", file_path=file_path)
    assert resolved_vars["MY_VAR"] == "default_value"
    assert resolved_vars["ANOTHER_VAR"] == "dev_value"

    # Test get_all_envs
    from src.envars.main import get_all_envs

    all_envs = get_all_envs(loc=None, file_path=file_path)
    assert "dev" in all_envs
    assert all_envs["dev"]["MY_VAR"] == "default_value"
    assert all_envs["dev"]["ANOTHER_VAR"] == "dev_value"


def test_resolve_cloudformation_export(tmp_path, monkeypatch):
    """Test that cloudformation_export: values are resolved correctly."""
    yaml_content = """
configuration:
  kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
  environments:
    - dev
  locations:
    - aws: "12345"

environment_variables:
  MY_EXPORT:
    default: "cloudformation_export:my-cf-export"
"""
    file_path = create_yaml_file(tmp_path, yaml_content)
    manager = load_from_yaml(file_path)

    # Mock the CloudFormationExports class
    mock_cf_exports = MagicMock()
    mock_cf_exports.get_export_value.return_value = "my-cf-export-value"
    monkeypatch.setattr("src.envars.main.CloudFormationExports", lambda: mock_cf_exports)

    resolved_vars = _get_resolved_variables(manager, loc="aws", env="dev", decrypt=True)

    assert "MY_EXPORT" in resolved_vars
    assert resolved_vars["MY_EXPORT"] == "my-cf-export-value"
    mock_cf_exports.get_export_value.assert_called_once_with("my-cf-export")


def test_resolve_jinja2_template(tmp_path, monkeypatch):
    """Test that Jinja2 templates are resolved correctly."""
    yaml_content = """
configuration:
  environments:
    - dev
  locations:
    - local: "local"

environment_variables:
  GREETING:
    default: "Hello"
  NAME:
    default: "World"
  MESSAGE:
    default: "{{ GREETING }}, {{ NAME }}!"
  SHELL_VAR:
    default: "Value is: {{ env.get('MY_SHELL_VAR', 'default') }}"
"""
    file_path = create_yaml_file(tmp_path, yaml_content)
    manager = load_from_yaml(file_path)

    # Test with shell variable set
    monkeypatch.setenv("MY_SHELL_VAR", "from_shell")
    resolved_vars = _get_resolved_variables(manager, loc="local", env="dev", decrypt=True)
    assert resolved_vars["MESSAGE"] == "Hello, World!"
    assert resolved_vars["SHELL_VAR"] == "Value is: from_shell"

    # Test with shell variable not set (should use default)
    monkeypatch.delenv("MY_SHELL_VAR", raising=False)
    resolved_vars = _get_resolved_variables(manager, loc="local", env="dev", decrypt=True)
    assert resolved_vars["SHELL_VAR"] == "Value is: default"


def test_resolve_template_with_undefined_variable_raises_error(tmp_path):
    """Test that a template with an undefined variable raises a ValueError."""
    yaml_content = """
configuration:
  environments:
    - dev
  locations:
    - local: "local"

environment_variables:
  MESSAGE:
    default: "Hello, {{ UNDEFINED_VAR }}"
"""
    file_path = create_yaml_file(tmp_path, yaml_content)
    manager = load_from_yaml(file_path)

    with pytest.raises(
        ValueError, match="Error rendering template for variable 'MESSAGE': 'UNDEFINED_VAR' is undefined"
    ):
        _get_resolved_variables(manager, loc="local", env="dev", decrypt=True)
