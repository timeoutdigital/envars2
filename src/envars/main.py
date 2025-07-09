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


class Secret(str):
    pass


def secret_representer(dumper, data):
    return dumper.represent_scalar("!secret", str(data), style="|")


def secret_constructor(loader, node):
    value = loader.construct_scalar(node)
    return Secret(value)


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
    yaml.add_constructor("!secret", secret_constructor, Loader=SafeLoaderWithDuplicatesCheck)
    with open(file_path) as f:
        data = yaml.load(f, Loader=SafeLoaderWithDuplicatesCheck)

    if data is None:
        return VariableManager()

    # Load global KMS key
    kms_key = data.get("configuration", {}).get("kms_key")
    app = data.get("configuration", {}).get("app")
    description_mandatory = data.get("configuration", {}).get("description_mandatory", False)
    manager = VariableManager(app=app, kms_key=kms_key, description_mandatory=description_mandatory)

    # Load environments
    for env_name in data.get("configuration", {}).get("environments", []):
        manager.add_environment(Environment(name=env_name))

    # Load locations
    for acc_data in data.get("configuration", {}).get("locations", []):
        for acc_name, acc_details in acc_data.items():
            if isinstance(acc_details, dict):
                location_id = acc_details.get("id")
                kms_key = acc_details.get("kms_key")
                manager.add_location(Location(name=acc_name, location_id=location_id, kms_key=kms_key))
            else:
                manager.add_location(Location(name=acc_name, location_id=acc_details))

    # Load environment variables
    for var_name, var_data in data.get("environment_variables", {}).items():
        if var_name.upper() != var_name:
            raise ValueError(f"Variable name '{var_name}' must be uppercase.")
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
                        if loc_name in [l.name for l in manager.locations.values()]:
                            loc = next((loc for loc in manager.locations.values() if loc.name == loc_name), None)
                            if loc:
                                if isinstance(loc_value, dict):
                                    raise ValueError(f"Invalid nesting in '{var_name}' -> '{env_name}' -> '{loc_name}'")
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
                            raise ValueError(f"Location '{loc_name}' not found in configuration.")
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
                                if isinstance(env_value, dict):
                                    raise ValueError(f"Invalid nesting in '{var_name}' -> '{loc_name}' -> '{env_name}'")
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
                                raise ValueError(f"Environment '{env_name}' not found in configuration.")
                    else:
                        manager.add_variable_value(
                            VariableValue(
                                variable_name=var_name,
                                value=value,
                                scope_type="LOCATION",
                                location_id=loc.location_id,
                            )
                        )
            else:
                raise ValueError(f"'{key}' is not a valid environment or location.")

    return manager


def write_envars_yml(manager: VariableManager, file_path: str):
    """Writes the VariableManager data to a YAML file."""
    yaml.add_representer(Secret, secret_representer, Dumper=yaml.Dumper)
    locations_data = []
    for loc in sorted(manager.locations.values(), key=lambda x: x.name):
        if loc.kms_key:
            locations_data.append({loc.name: {"id": loc.location_id, "kms_key": loc.kms_key}})
        else:
            locations_data.append({loc.name: loc.location_id})

    data = {
        "configuration": {
            "app": manager.app,
            "kms_key": manager.kms_key,
            "description_mandatory": manager.description_mandatory,
            "environments": sorted(manager.environments.keys()),
            "locations": locations_data,
        },
        "environment_variables": {},
    }

    # Populate environment_variables
    sorted_vars = sorted(manager.variables.items())
    for var_name, variable in sorted_vars:
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
                    loc_name = next(
                        (loc.name for loc in manager.locations.values() if loc.location_id == vv.location_id),
                        None,
                    )
                    if loc_name:
                        loc_values[loc_name] = vv.value
                elif vv.scope_type == "SPECIFIC":
                    loc_name = next(
                        (loc.name for loc in manager.locations.values() if loc.location_id == vv.location_id),
                        None,
                    )
                    if loc_name:
                        if vv.environment_name not in specific_values:
                            specific_values[vv.environment_name] = {}
                        specific_values[vv.environment_name][loc_name] = vv.value

        if default_value is not None:
            var_data["default"] = default_value

        for env, value in sorted(env_values.items()):
            var_data[env] = value

        for loc, value in sorted(loc_values.items()):
            var_data[loc] = value

        for env, loc_data in sorted(specific_values.items()):
            if env in var_data and isinstance(var_data[env], dict):
                var_data[env].update(sorted(loc_data.items()))
            else:
                var_data[env] = dict(sorted(loc_data.items()))

        data["environment_variables"][var_name] = var_data

    with open(file_path, "w") as f:
        # Dump configuration if it exists
        if any(data["configuration"].values()):
            config_data = {"configuration": data["configuration"]}
            # Sort locations list of dicts
            config_data["configuration"]["locations"] = sorted(
                config_data["configuration"]["locations"],
                key=lambda x: list(x.keys())[0],
            )
            yaml.dump(config_data, f, sort_keys=False, Dumper=yaml.Dumper)
            f.write("\n")

        # Dump environment variables
        if data["environment_variables"]:
            f.write("environment_variables:\n")

            # Sort variables for consistent output
            sorted_env_vars = sorted(data["environment_variables"].items())

            for i, (var_name, var_data) in enumerate(sorted_env_vars):
                var_dict = {var_name: var_data}
                var_yaml_str = yaml.dump(
                    var_dict,
                    sort_keys=False,
                    indent=2,
                    Dumper=yaml.Dumper,
                    default_flow_style=False,
                )

                # Indent the whole block
                indented_var_yaml = "".join(["  " + line + "\n" for line in var_yaml_str.splitlines()])
                f.write(indented_var_yaml)

                if i < len(sorted_env_vars) - 1:
                    f.write("\n")


if __name__ == "__main__":
    try:
        manager = load_from_yaml("envars.yml")

        print("--- Loaded Data ---")
        print(f"App: {manager.app}")
        print(f"KMS Key: {manager.kms_key}")
        print(f"Total VariableValues loaded: {len(manager.variable_values)}")
        print("Variables:", list(manager.variables.keys()))
        print("Environments:", list(manager.environments.keys()))
        print("Locations:", [loc.name for loc in manager.locations.values()])

        print("\n--- Retrieving Variable Values ---")
        test_var = manager.get_variable("TEST", "prod")
        print(f"TEST (prod): {test_var.value if test_var else None}")
        test2_var = manager.get_variable("TEST2", "prod")
        print(f"TEST2 (prod): {test2_var.value if test2_var else None}")
        test3_var = manager.get_variable("TEST3")
        print(f"TEST3 (default): {test3_var.value if test3_var else None}")
        test3_var_specific = manager.get_variable("TEST3", "prod", "sandbox")
        print(f"TEST3 (sandbox, prod): {test3_var_specific.value if test3_var_specific else None}")
        test4_var_specific = manager.get_variable("TEST4", "prod", "sandbox")
        print(f"TEST4 (prod, sandbox): {test4_var_specific.value if test4_var_specific else None}")
    except DuplicateKeyError as e:
        print(f"Error: {e}")
