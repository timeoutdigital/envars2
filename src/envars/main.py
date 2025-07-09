import yaml

from src.envars.models import (
    Environment,
    Location,
    Variable,
    VariableManager,
    VariableValue,
)


class DuplicateKeyError(Exception):
    pass


class SafeLoaderWithDuplicatesCheck(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise DuplicateKeyError(f"Duplicate key: {key}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def load_from_yaml(file_path: str) -> VariableManager:
    """Loads variables, environments, locations, and values from a YAML file."""
    manager = VariableManager()
    with open(file_path) as f:
        data = yaml.load(f, Loader=SafeLoaderWithDuplicatesCheck)

    if data is None:
        return manager

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
                if loc:
                    if isinstance(value, dict):
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
                    else:
                        manager.add_variable_value(
                            VariableValue(
                                variable_name=var_name,
                                value=value,
                                scope_type="LOCATION",
                                location_id=loc.location_id,
                            )
                        )

    return manager


def write_envars_yml(manager: VariableManager, file_path: str):
    """Writes the VariableManager data to a YAML file."""
    data = {
        "configuration": {
            "environments": [],
            "accounts": [],
        },
        "environment_variables": {},
    }

    # Populate environments
    for env_name in manager.environments.keys():
        data["configuration"]["environments"].append(env_name)

    # Populate accounts
    for loc in manager.locations.values():
        data["configuration"]["accounts"].append({loc.name: loc.location_id})

    # Populate environment_variables
    for var_name, variable in manager.variables.items():
        var_data = {}
        if variable.description:
            var_data["description"] = variable.description

        # Group variable values by scope
        default_value = None
        env_values = {}
        loc_values = {}
        specific_values = {}

        for vv in manager.variable_values:
            if vv.variable_name == var_name:
                if vv.scope_type == "DEFAULT":
                    default_value = vv.value
                elif vv.scope_type == "ENVIRONMENT":
                    env_values[vv.environment_name] = vv.value
                elif vv.scope_type == "LOCATION":
                    loc_values[
                        next(loc.name for loc in manager.locations.values() if loc.location_id == vv.location_id)
                    ] = vv.value
                elif vv.scope_type == "SPECIFIC":
                    if vv.environment_name not in specific_values:
                        specific_values[vv.environment_name] = {}
                    specific_values[vv.environment_name][
                        next(loc.name for loc in manager.locations.values() if loc.location_id == vv.location_id)
                    ] = vv.value

        if default_value is not None:
            var_data["default"] = default_value

        for env, value in env_values.items():
            var_data[env] = value

        for loc, value in loc_values.items():
            var_data[loc] = value

        for env, loc_data in specific_values.items():
            if env in var_data and isinstance(var_data[env], dict):
                var_data[env].update(loc_data)
            else:
                var_data[env] = loc_data

        data["environment_variables"][var_name] = var_data

    with open(file_path, "w") as f:
        yaml.dump(data, f, sort_keys=False)


if __name__ == "__main__":
    try:
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
    except DuplicateKeyError as e:
        print(f"Error: {e}")
