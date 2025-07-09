import yaml

from envars.models import (
    Environment,
    Location,
    Variable,
    VariableManager,
    VariableValue,
)


def load_from_yaml(file_path: str) -> VariableManager:
    """Loads variables, environments, locations, and values from a YAML file."""
    manager = VariableManager()
    with open(file_path) as f:
        data = yaml.safe_load(f)

    # Load environments
    for env_name in data.get("configuration", {}).get("environments", []):
        manager.add_environment(Environment(name=env_name))

    # Load locations (accounts)
    for acc_data in data.get("configuration", {}).get("accounts", []):
        for acc_name, acc_id in acc_data.items():
            manager.add_location(Location(name=acc_name, location_id=acc_id))

    # Load environment variables
    for var_name, var_data in data.get("environment_variables", {}).items():
        manager.add_variable(Variable(name=var_name, description=var_data.get("description")))

        if "default" in var_data:
            manager.add_variable_value(
                VariableValue(
                    variable_name=var_name,
                    value=var_data["default"],
                    scope_type="DEFAULT",
                )
            )

        for key, value in var_data.items():
            if key in ["description", "default"]:
                continue

            if key in manager.environments:
                env_name = key
                if isinstance(value, dict):
                    for loc_name, loc_value in value.items():
                        loc = next((loc for loc in manager.locations.values() if loc.name == loc_name), None)
                        if loc:
                            manager.add_variable_value(
                                VariableValue(
                                    variable_name=var_name,
                                    value=loc_value,
                                    scope_type="SPECIFIC",
                                    environment_name=env_name,
                                    location_id=loc.location_id,
                                )
                            )
                else:
                    manager.add_variable_value(
                        VariableValue(
                            variable_name=var_name,
                            value=value,
                            scope_type="ENVIRONMENT",
                            environment_name=env_name,
                        )
                    )
            elif key in [loc.name for loc in manager.locations.values()]:
                loc_name = key
                loc = next((loc for loc in manager.locations.values() if loc.name == loc_name), None)
                if loc and isinstance(value, dict):
                    for env_name, env_value in value.items():
                        if env_name in manager.environments:
                            manager.add_variable_value(
                                VariableValue(
                                    variable_name=var_name,
                                    value=env_value,
                                    scope_type="SPECIFIC",
                                    environment_name=env_name,
                                    location_id=loc.location_id,
                                )
                            )

    return manager


if __name__ == "__main__":
    manager = load_from_yaml("envars.yml")

    print("--- Loaded Data ---")
    print(f"Total VariableValues loaded: {len(manager.variable_values)}")
    print("Variables:", list(manager.variables.keys()))
    print("Environments:", list(manager.environments.keys()))
    print("Locations:", [loc.name for loc in manager.locations.values()])

    print("\n--- Retrieving Variable Values ---")
    print(f"TEST (prod): {manager.get_variable_value('TEST', 'prod')}")
    print(f"TEST2 (prod): {manager.get_variable_value('TEST2', 'prod')}")
    print(f"TEST3 (default): {manager.get_variable_value('TEST3')}")
    print(f"TEST3 (sandbox, prod): {manager.get_variable_value('TEST3', 'prod', 'sandbox')}")
    print(f"TEST4 (prod, sandbox): {manager.get_variable_value('TEST4', 'prod', 'sandbox')}")
