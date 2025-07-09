import pytest
import yaml

from src.envars.main import DuplicateKeyError, SafeLoaderWithDuplicatesCheck, load_from_yaml, write_envars_yml
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
  kms_key: null
  environments:
  - dev
  - prod
  accounts:
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
                expected_value = manager.get_variable_value(var_name, env_name, loc_name)
                actual_value = loaded_manager.get_variable_value(var_name, env_name, loc_name)
                assert expected_value == actual_value


def test_load_from_yaml_with_kms_key(tmp_path):
    yaml_content = """
configuration:
  kms_key: "global-kms-key"
  environments:
    - prod
  accounts:
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
