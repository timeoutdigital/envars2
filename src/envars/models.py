import uuid
from typing import Any


class Variable:
    """Represents a generic configuration variable, identified by its unique name."""

    def __init__(self, name: str, description: str | None = None):
        # The name is the unique identifier for the variable.
        self.name: str = name
        self.description: str | None = description

    def to_dict(self) -> dict[str, Any]:
        """Converts the Variable object to a dictionary."""
        return {
            "name": self.name,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Creates a Variable object from a dictionary."""
        var = cls(name=data["name"], description=data.get("description"))
        return var

    def __repr__(self):
        """Returns readable representation."""
        return f"Variable(name='{self.name}')"


class Environment:
    """Represents different deployment or operational environments."""

    def __init__(self, name: str, description: str | None = None):
        self.name: str = name
        self.description: str | None = description

    def to_dict(self) -> dict[str, Any]:
        """Converts the Environment object to a dictionary."""
        return {
            "name": self.name,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Creates an Environment object from a dictionary."""
        env = cls(
            name=data["name"],
            description=data.get("description"),
        )
        return env

    def __repr__(self):
        """Returns readable representation."""
        return f"Environment(name='{self.name}')"


class Location:
    """Represents a location where variables are deployed, like an AWS account or a GCP project."""

    def __init__(self, name: str, location_id: str | None = None, kms_key: str | None = None):
        self.location_id: str = location_id if location_id else str(uuid.uuid4())
        self.name: str = name
        self.kms_key: str | None = kms_key

    def to_dict(self) -> dict[str, Any]:
        """Converts the Location object to a dictionary."""
        return {
            "location_id": self.location_id,
            "name": self.name,
            "kms_key": self.kms_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Creates a Location object from a dictionary."""
        loc = cls(name=data["name"], location_id=data["location_id"], kms_key=data.get("kms_key"))
        return loc

    def __repr__(self):
        """Returns readable representation."""
        return f"Location(id='{self.location_id}', name='{self.name}')"


class VariableValue:
    """This entity stores the actual value of a Variable.

    for a specific Environment and Location, or acts as a default value based on its scope.
    """

    SCOPES = ["DEFAULT", "ENVIRONMENT", "LOCATION", "SPECIFIC"]

    def __init__(
        self,
        variable_name: str,
        value: Any,
        scope_type: str,
        environment_name: str | None = None,
        location_id: str | None = None,
        is_encrypted: bool = False,
        variable_value_id: str | None = None,
    ):
        if scope_type not in self.SCOPES:
            raise ValueError(f"Invalid scope_type. Must be one of {self.SCOPES}")

        # Validate environment_name and location_id based on scope_type
        if scope_type == "DEFAULT" and (environment_name is not None or location_id is not None):
            raise ValueError("For 'DEFAULT' scope, environment_name and location_id must be None.")
        if scope_type == "ENVIRONMENT" and (environment_name is None or location_id is not None):
            raise ValueError("For 'ENVIRONMENT' scope, environment_name must be provided and location_id must be None.")
        if scope_type == "LOCATION" and (environment_name is not None or location_id is None):
            raise ValueError("For 'LOCATION' scope, location_id must be provided and environment_name must be None.")
        if scope_type == "SPECIFIC" and (environment_name is None or location_id is None):
            raise ValueError("For 'SPECIFIC' scope, both environment_name and location_id must be provided.")

        self.variable_value_id: str = variable_value_id if variable_value_id else str(uuid.uuid4())
        self.variable_name: str = variable_name
        self.environment_name: str | None = environment_name
        self.location_id: str | None = location_id
        self.scope_type: str = scope_type
        self.value: str = value
        self.is_encrypted: bool = is_encrypted

    def to_dict(self) -> dict[str, Any]:
        """Converts the VariableValue object to a dictionary."""
        return {
            "variable_value_id": self.variable_value_id,
            "variable_name": self.variable_name,
            "environment_name": self.environment_name,
            "location_id": self.location_id,
            "scope_type": self.scope_type,
            "value": self.value,
            "is_encrypted": self.is_encrypted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Creates a VariableValue object from a dictionary."""
        vv = cls(
            variable_name=data["variable_name"],
            value=data["value"],
            scope_type=data["scope_type"],
            environment_name=data.get("environment_name"),
            location_id=data.get("location_id"),
            is_encrypted=data.get("is_encrypted", False),
            variable_value_id=data["variable_value_id"],
        )
        return vv

    def __repr__(self):
        """Returns readable representation."""
        env_str = f"env='{self.environment_name}'" if self.environment_name else "env=None"
        loc_str = f"loc='{self.location_id}'" if self.location_id else "loc=None"
        return (
            f"VariableValue(id='{self.variable_value_id}', var_name='{self.variable_name}', "
            f"scope='{self.scope_type}', {env_str}, {loc_str}, value='{self.value}')"
        )


class VariableManager:
    """Manages the collection of Variables, Environments, Locations, and VariableValues.

    Provides methods to retrieve variable values based on the defined hierarchy.
    In a real application, this would interact with a database.
    """

    def __init__(self, app: str | None = None, kms_key: str | None = None, description_mandatory: bool = False):
        self.app = app
        self.variables: dict[str, Variable] = {}
        self.environments: dict[str, Environment] = {}
        self.locations: dict[str, Location] = {}
        self.variable_values: list[VariableValue] = []
        self.kms_key = kms_key
        self.description_mandatory = description_mandatory

    def add_variable(self, variable: Variable):
        """Adds a Variable to the manager."""
        if variable.name in self.variables:
            raise ValueError(f"Variable with name '{variable.name}' already exists.")
        self.variables[variable.name] = variable

    def add_environment(self, environment: Environment):
        """Adds an Environment to the manager."""
        if environment.name in self.environments:
            raise ValueError(f"Environment with name '{environment.name}' already exists.")
        self.environments[environment.name] = environment

    def add_location(self, location: Location):
        """Adds a Location to the manager."""
        if location.location_id in self.locations:
            raise ValueError(f"Location with ID {location.location_id} already exists.")
        self.locations[location.location_id] = location

    def add_variable_value(self, var_value: VariableValue):
        """Adds a VariableValue to the manager."""
        # Basic check for uniqueness based on scope type
        for existing_vv in self.variable_values:
            if existing_vv.variable_name == var_value.variable_name and existing_vv.scope_type == var_value.scope_type:
                if var_value.scope_type == "DEFAULT":
                    raise ValueError(f"Default value for variable '{var_value.variable_name}' already exists.")
                elif (
                    var_value.scope_type == "ENVIRONMENT" and existing_vv.environment_name == var_value.environment_name
                ):
                    raise ValueError(
                        f"""Environment-specific value for variable '{var_value.variable_name}'
                        in env '{var_value.environment_name}' already exists."""
                    )
                elif var_value.scope_type == "LOCATION" and existing_vv.location_id == var_value.location_id:
                    raise ValueError(
                        f"""Location-specific value for variable '{var_value.variable_name}' for
                        loc {var_value.location_id} already exists."""
                    )
                elif (
                    var_value.scope_type == "SPECIFIC"
                    and existing_vv.environment_name == var_value.environment_name
                    and existing_vv.location_id == var_value.location_id
                ):
                    raise ValueError(
                        f"""Specific value for variable '{var_value.variable_name}' in
                        env '{var_value.environment_name}' for loc {var_value.location_id} already exists."""
                    )
        self.variable_values.append(var_value)

    def get_variable(
        self,
        variable_name: str,
        environment_name: str | None = None,
        location_name: str | None = None,
    ) -> VariableValue | None:
        """Retrieves the most specific value for a variable based on the context.

        The hierarchy is:
        1. Specific (Environment + Location)
        2. Environment-specific
        3. Location-specific
        4. Default.
        """
        if variable_name not in self.variables:
            return None

        if environment_name and environment_name not in self.environments:
            pass

        loc_id = None
        if location_name:
            loc = next((lo for lo in self.locations.values() if lo.name == location_name), None)
            if loc:
                loc_id = loc.location_id

        # Collect all potential values for the variable
        candidate_values = [vv for vv in self.variable_values if vv.variable_name == variable_name]

        # Refined logic to ensure correct fallback
        # 1. Try for SPECIFIC
        if environment_name and loc_id:
            specific_val = next(
                (
                    vv
                    for vv in candidate_values
                    if vv.scope_type == "SPECIFIC"
                    and vv.environment_name == environment_name
                    and vv.location_id == loc_id
                ),
                None,
            )
            if specific_val:
                return specific_val

        # 2. Try for ENVIRONMENT
        if environment_name:
            env_val = next(
                (
                    vv
                    for vv in candidate_values
                    if vv.scope_type == "ENVIRONMENT" and vv.environment_name == environment_name
                ),
                None,
            )
            if env_val:
                return env_val

        # 3. Try for LOCATION
        if loc_id:
            loc_val = next(
                (vv for vv in candidate_values if vv.scope_type == "LOCATION" and vv.location_id == loc_id), None
            )
            if loc_val:
                return loc_val

        # 4. Fallback to DEFAULT
        default_val = next((vv for vv in candidate_values if vv.scope_type == "DEFAULT"), None)
        if default_val:
            return default_val

        return None


# --- Example Usage ---
if __name__ == "__main__":
    manager = VariableManager(app="ExampleApp")

    # 1. Define Variables
    api_key_var = Variable(name="API_KEY", description="API Key for external service")
    db_url_var = Variable(name="DATABASE_URL", description="Database connection string")
    manager.add_variable(api_key_var)
    manager.add_variable(db_url_var)

    # 2. Define Environments
    dev_env = Environment(name="Development")
    prod_env = Environment(name="Production")
    qa_env = Environment(name="QA")
    manager.add_environment(dev_env)
    manager.add_environment(prod_env)
    manager.add_environment(qa_env)

    # 3. Define Locations
    aws_location = Location(name="AWS Account 1")
    gcp_location = Location(name="GCP Project Main")
    manager.add_location(aws_location)
    manager.add_location(gcp_location)

    # 4. Add Variable Values with different scopes

    # Default value for API_KEY
    manager.add_variable_value(
        VariableValue(variable_name=api_key_var.name, value="DEFAULT_API_KEY", scope_type="DEFAULT")
    )

    # Environment-specific default for API_KEY in Development
    manager.add_variable_value(
        VariableValue(
            variable_name=api_key_var.name,
            environment_name=dev_env.name,
            value="DEV_API_KEY_DEFAULT",
            scope_type="ENVIRONMENT",
        )
    )

    # Location-specific default for DATABASE_URL for AWS Location
    manager.add_variable_value(
        VariableValue(
            variable_name=db_url_var.name,
            location_id=aws_location.location_id,
            value="AWS_DB_DEFAULT_URL",
            scope_type="LOCATION",
        )
    )

    # Specific value for API_KEY in Production for AWS Location
    manager.add_variable_value(
        VariableValue(
            variable_name=api_key_var.name,
            environment_name=prod_env.name,
            location_id=aws_location.location_id,
            value="AWS_PROD_API_KEY_SECURE",
            scope_type="SPECIFIC",
            is_encrypted=True,
        )
    )

    # Specific value for API_KEY in Development for GCP Location
    manager.add_variable_value(
        VariableValue(
            variable_name=api_key_var.name,
            environment_name=dev_env.name,
            location_id=gcp_location.location_id,
            value="GCP_DEV_API_KEY_TEST",
            scope_type="SPECIFIC",
        )
    )

    print("\n--- Retrieving Variable Values ---")

    # Test Cases for API_KEY
    print(f"API_KEY (AWS, Prod): {manager.get_variable('API_KEY', 'Production', 'AWS Account 1')}")
    # Expected: AWS_PROD_API_KEY_SECURE (Specific)

    print(f"API_KEY (AWS, Dev): {manager.get_variable('API_KEY', 'Development', 'AWS Account 1')}")
    # Expected: DEV_API_KEY_DEFAULT (Environment-specific, as no specific for AWS/Dev)

    print(f"API_KEY (GCP, Dev): {manager.get_variable('API_KEY', 'Development', 'GCP Project Main')}")
    # Expected: GCP_DEV_API_KEY_TEST (Specific)

    print(f"API_KEY (GCP, Prod): {manager.get_variable('API_KEY', 'Production', 'GCP Project Main')}")
    # Expected: DEFAULT_API_KEY (Default, as no specific or env-specific for GCP/Prod)

    print(f"API_KEY (AWS, QA): {manager.get_variable('API_KEY', 'QA', 'AWS Account 1')}")
    # Expected: DEFAULT_API_KEY (Default, as no specific or env-specific for AWS/QA)

    # Test Cases for DATABASE_URL
    print(f"DATABASE_URL (AWS, Prod): {manager.get_variable('DATABASE_URL', 'Production', 'AWS Account 1')}")
    # Expected: AWS_DB_DEFAULT_URL (Location-specific)

    print(f"DATABASE_URL (GCP, Dev): {manager.get_variable('DATABASE_URL', 'Development', 'GCP Project Main')}")
    # Expected: None (No value defined, and no default for DATABASE_URL)

    # Test for non-existent variable
    print(f"NON_EXISTENT_VAR (AWS, Prod): {manager.get_variable('NON_EXISTENT_VAR', 'Production', 'AWS Account 1')}")
    # Expected: None
