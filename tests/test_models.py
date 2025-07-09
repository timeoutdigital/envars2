import uuid

import pytest

from src.envars.models import (
    Environment,
    Location,
    Variable,
    VariableManager,
    VariableValue,
)


# Tests for Variable class
def test_variable_creation():
    var = Variable(name="API_KEY", description="Test API Key")
    assert var.name == "API_KEY"
    assert var.description == "Test API Key"


def test_variable_to_dict():
    var = Variable(name="API_KEY", description="Test API Key")
    var_dict = var.to_dict()
    assert var_dict == {"name": "API_KEY", "description": "Test API Key"}


def test_variable_from_dict():
    var_data = {"name": "API_KEY", "description": "Test API Key"}
    var = Variable.from_dict(var_data)
    assert var.name == "API_KEY"
    assert var.description == "Test API Key"


def test_variable_repr():
    var = Variable(name="API_KEY")
    assert repr(var) == "Variable(name='API_KEY')"


# Tests for Environment class
def test_environment_creation():
    env = Environment(name="Production", description="Production environment")
    assert env.name == "Production"
    assert env.description == "Production environment"


def test_environment_to_dict():
    env = Environment(name="Production", description="Production environment")
    env_dict = env.to_dict()
    assert env_dict == {"name": "Production", "description": "Production environment"}


def test_environment_from_dict():
    env_data = {"name": "Production", "description": "Production environment"}
    env = Environment.from_dict(env_data)
    assert env.name == "Production"
    assert env.description == "Production environment"


def test_environment_repr():
    env = Environment(name="Production")
    assert repr(env) == "Environment(name='Production')"


# Tests for Location class
def test_location_creation():
    loc = Location(name="AWS us-east-1")
    assert loc.name == "AWS us-east-1"
    assert isinstance(uuid.UUID(loc.location_id), uuid.UUID)


def test_location_creation_with_id():
    loc_id = str(uuid.uuid4())
    loc = Location(name="AWS us-east-1", location_id=loc_id)
    assert loc.location_id == loc_id


def test_location_to_dict():
    loc_id = str(uuid.uuid4())
    loc = Location(name="AWS us-east-1", location_id=loc_id)
    loc_dict = loc.to_dict()
    assert loc_dict == {"location_id": loc_id, "name": "AWS us-east-1", "kms_key": None}


def test_location_from_dict():
    loc_id = str(uuid.uuid4())
    loc_data = {"location_id": loc_id, "name": "AWS us-east-1", "kms_key": "some-key"}
    loc = Location.from_dict(loc_data)
    assert loc.name == "AWS us-east-1"
    assert loc.location_id == loc_id
    assert loc.kms_key == "some-key"


def test_location_repr():
    loc_id = str(uuid.uuid4())
    loc = Location(name="AWS us-east-1", location_id=loc_id)
    assert repr(loc) == f"Location(id='{loc_id}', name='AWS us-east-1')"


# Tests for VariableValue class
def test_variable_value_creation_default():
    vv = VariableValue(variable_name="API_KEY", value="default_value", scope_type="DEFAULT")
    assert vv.scope_type == "DEFAULT"
    assert vv.environment_name is None
    assert vv.location_id is None


def test_variable_value_creation_environment():
    vv = VariableValue(
        variable_name="API_KEY",
        value="dev_value",
        scope_type="ENVIRONMENT",
        environment_name="Development",
    )
    assert vv.scope_type == "ENVIRONMENT"
    assert vv.environment_name == "Development"
    assert vv.location_id is None


def test_variable_value_creation_location():
    loc_id = str(uuid.uuid4())
    vv = VariableValue(
        variable_name="API_KEY",
        value="loc_value",
        scope_type="LOCATION",
        location_id=loc_id,
    )
    assert vv.scope_type == "LOCATION"
    assert vv.environment_name is None
    assert vv.location_id == loc_id


def test_variable_value_creation_specific():
    loc_id = str(uuid.uuid4())
    vv = VariableValue(
        variable_name="API_KEY",
        value="specific_value",
        scope_type="SPECIFIC",
        environment_name="Production",
        location_id=loc_id,
    )
    assert vv.scope_type == "SPECIFIC"
    assert vv.environment_name == "Production"
    assert vv.location_id == loc_id


def test_variable_value_invalid_scope():
    with pytest.raises(ValueError):
        VariableValue(variable_name="API_KEY", value="val", scope_type="INVALID_SCOPE")


@pytest.mark.parametrize(
    "scope_type,env_name,loc_id,should_raise",
    [
        ("DEFAULT", "Dev", None, True),
        ("DEFAULT", None, "loc1", True),
        ("ENVIRONMENT", None, None, True),
        ("ENVIRONMENT", "Dev", "loc1", True),
        ("LOCATION", "Dev", "loc1", True),
        ("LOCATION", None, None, True),
        ("SPECIFIC", None, "loc1", True),
        ("SPECIFIC", "Dev", None, True),
    ],
)
def test_variable_value_scope_validation(scope_type, env_name, loc_id, should_raise):
    if should_raise:
        with pytest.raises(ValueError):
            VariableValue(
                variable_name="VAR",
                value="val",
                scope_type=scope_type,
                environment_name=env_name,
                location_id=loc_id,
            )
    else:
        VariableValue(
            variable_name="VAR",
            value="val",
            scope_type=scope_type,
            environment_name=env_name,
            location_id=loc_id,
        )


def test_variable_value_to_from_dict():
    loc_id = str(uuid.uuid4())
    vv_id = str(uuid.uuid4())
    vv = VariableValue(
        variable_name="API_KEY",
        value="specific_value",
        scope_type="SPECIFIC",
        environment_name="Production",
        location_id=loc_id,
        is_encrypted=True,
        variable_value_id=vv_id,
    )
    vv_dict = vv.to_dict()
    assert vv_dict == {
        "variable_value_id": vv_id,
        "variable_name": "API_KEY",
        "environment_name": "Production",
        "location_id": loc_id,
        "scope_type": "SPECIFIC",
        "value": "specific_value",
        "is_encrypted": True,
    }
    vv_from_dict = VariableValue.from_dict(vv_dict)
    assert vv_from_dict.variable_value_id == vv_id
    assert vv_from_dict.variable_name == "API_KEY"
    assert vv_from_dict.scope_type == "SPECIFIC"
    assert vv_from_dict.value == "specific_value"


# Tests for VariableManager class
@pytest.fixture
def manager():
    """Provides a VariableManager instance populated with test data."""
    m = VariableManager()
    # Variables
    m.add_variable(Variable(name="API_KEY", description="API Key"))
    m.add_variable(Variable(name="DB_URL", description="Database URL"))
    # Environments
    m.add_environment(Environment(name="Dev"))
    m.add_environment(Environment(name="Prod"))
    # Locations
    aws_loc = Location(name="AWS")
    gcp_loc = Location(name="GCP")
    m.add_location(aws_loc)
    m.add_location(gcp_loc)
    # VariableValues
    m.add_variable_value(VariableValue(variable_name="API_KEY", value="default_key", scope_type="DEFAULT"))
    m.add_variable_value(
        VariableValue(
            variable_name="API_KEY",
            value="dev_key",
            scope_type="ENVIRONMENT",
            environment_name="Dev",
        )
    )
    m.add_variable_value(
        VariableValue(
            variable_name="DB_URL",
            value="aws_db",
            scope_type="LOCATION",
            location_id=aws_loc.location_id,
        )
    )
    m.add_variable_value(
        VariableValue(
            variable_name="API_KEY",
            value="prod_aws_key",
            scope_type="SPECIFIC",
            environment_name="Prod",
            location_id=aws_loc.location_id,
        )
    )
    return m


def test_add_duplicate_variable(manager):
    with pytest.raises(ValueError):
        manager.add_variable(Variable(name="API_KEY"))


def test_add_duplicate_environment(manager):
    with pytest.raises(ValueError):
        manager.add_environment(Environment(name="Dev"))


def test_add_duplicate_location(manager):
    with pytest.raises(ValueError):
        aws_loc = next(loc for loc in manager.locations.values() if loc.name == "AWS")
        manager.add_location(Location(name="AWS", location_id=aws_loc.location_id))


def test_add_duplicate_variable_value(manager):
    with pytest.raises(ValueError):
        manager.add_variable_value(
            VariableValue(variable_name="API_KEY", value="another_default", scope_type="DEFAULT")
        )


def test_get_value_specific(manager):
    val = manager.get_variable_value("API_KEY", "Prod", "AWS")
    assert val == "prod_aws_key"


def test_get_value_environment(manager):
    val = manager.get_variable_value("API_KEY", "Dev", "GCP")
    assert val == "dev_key"


def test_get_value_location(manager):
    val = manager.get_variable_value("DB_URL", "Prod", "AWS")
    assert val == "aws_db"


def test_get_value_default(manager):
    val = manager.get_variable_value("API_KEY", "Prod", "GCP")
    assert val == "default_key"


def test_get_value_no_value(manager):
    val = manager.get_variable_value("DB_URL", "Dev", "GCP")
    assert val is None


def test_get_value_non_existent_variable(manager):
    val = manager.get_variable_value("NON_EXISTENT", "Prod", "AWS")
    assert val is None


def test_get_value_non_existent_env_or_loc(manager):
    # Should fall back to default
    val = manager.get_variable_value("API_KEY", "NonExistentEnv", "AWS")
    assert val == "default_key"
    val = manager.get_variable_value("API_KEY", "Prod", "NonExistentLoc")
    assert val == "default_key"
