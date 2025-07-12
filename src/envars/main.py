import os
import sys
from collections import deque

import yaml
from jinja2 import Environment, meta

from .aws_cloudformation import CloudFormationExports
from .aws_kms import AWSKMSAgent
from .aws_ssm import SSMParameterStore
from .cloud_utils import get_default_location_name
from .gcp_kms import GCPKMSAgent
from .gcp_secret_manager import GCPSecretManager
from .models import (
    Environment as EnvarsEnvironment,
)
from .models import (
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
        manager.add_environment(EnvarsEnvironment(name=env_name))

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
        manager.add_variable(
            Variable(
                name=var_name,
                description=var_data.get("description"),
                validation=var_data.get("validation"),
            )
        )

        if "default" in var_data:
            manager.add_variable_value(
                VariableValue(
                    variable_name=var_name,
                    value=var_data["default"],
                    scope_type="DEFAULT",
                )
            )

        for key, value in var_data.items():
            if key in ["description", "default", "validation"]:
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
        if variable.validation:
            var_data["validation"] = variable.validation

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


def _get_decrypted_value(manager: VariableManager, vv: VariableValue):
    """Helper function to decrypt a single VariableValue."""
    if not isinstance(vv.value, Secret):
        return vv.value

    if not manager.kms_key:
        raise ValueError("Cannot decrypt without a kms_key in configuration.")

    # Get encryption context from the variable's scope
    encryption_context = {"app": manager.app or ""}
    if vv.environment_name:
        encryption_context["environment"] = vv.environment_name
    if vv.location_id:
        loc_name = next((l.name for l in manager.locations.values() if l.location_id == vv.location_id), None)
        if loc_name:
            encryption_context["location"] = loc_name

    try:
        # Determine KMS provider and decrypt
        if manager.kms_key.startswith("arn:aws:kms:"):
            agent = AWSKMSAgent()
            return agent.decrypt(str(vv.value), encryption_context)
        elif manager.kms_key.startswith("projects/"):
            agent = GCPKMSAgent()
            key_id = manager.kms_key
            return agent.decrypt(str(vv.value), key_id, encryption_context)
        else:
            raise ValueError(f"Unknown KMS key format: {manager.kms_key}")
    except Exception as e:
        raise ValueError(f"Error decrypting {vv.variable_name}: {e}") from e


def _check_for_circular_dependencies(variables: dict[str, str | Secret]):
    """Checks for circular dependencies in templated variables."""
    jinja_env = Environment(autoescape=True)
    adj = {v: [] for v in variables}
    in_degree = dict.fromkeys(variables, 0)
    for var_name, value in variables.items():
        if isinstance(value, str):
            try:
                ast = jinja_env.parse(value)
                deps = meta.find_undeclared_variables(ast) - {"env"}
                for dep in deps:
                    if dep in variables:
                        adj[dep].append(var_name)
                        in_degree[var_name] += 1
            except Exception as e:
                print(f"Could not parse template for {var_name}: {e}", file=sys.stderr)
    queue = deque([v for v in variables if in_degree[v] == 0])
    sorted_order = []
    while queue:
        u = queue.popleft()
        sorted_order.append(u)
        for v in adj.get(u, []):
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)
    if len(sorted_order) != len(variables):
        cycle_nodes = sorted(set(variables.keys()) - set(sorted_order))
        raise ValueError(f"Circular dependency detected in variables: {', '.join(cycle_nodes)}")
    return sorted_order


def _get_resolved_variables(
    manager: VariableManager,
    loc: str,
    env: str | None,
    decrypt: bool,
) -> dict[str, str | Secret]:
    """Helper function to get all resolved variables for a given context."""
    if env is None:
        env = os.environ.get("STAGE")
        if env is None:
            raise ValueError("The --env option is required if the STAGE environment variable is not set.")

    if env not in manager.environments:
        raise ValueError(f"Environment '{env}' not found in configuration.")

    if not any(l.name == loc for l in manager.locations.values()):
        raise ValueError(f"Location '{loc}' not found in configuration.")

    resolved_vars = {}
    for var_name in manager.variables:
        variable_value_obj = manager.get_variable(var_name, env, loc)
        if variable_value_obj:
            value = (
                _get_decrypted_value(manager, variable_value_obj)
                if decrypt and isinstance(variable_value_obj.value, Secret)
                else variable_value_obj.value
            )
            if value == "[DECRYPTION FAILED]":
                raise ValueError("Decryption failed")
            resolved_vars[var_name] = value

    # Template substitution with Jinja2
    sorted_order = _check_for_circular_dependencies(resolved_vars)
    jinja_env = Environment(autoescape=True)
    rendered = {}
    for var_name in sorted_order:
        value = resolved_vars[var_name]
        if isinstance(value, str):
            try:
                template = jinja_env.from_string(value)
                context = {"env": os.environ}
                context.update(rendered)
                rendered[var_name] = template.render(context)
            except Exception:
                rendered[var_name] = value
        else:
            rendered[var_name] = value
    resolved_vars = rendered

    # Parameter Store substitution
    ssm_store = SSMParameterStore()
    gcp_secret_manager = GCPSecretManager()
    cf_exports = CloudFormationExports()
    for var_name, value in resolved_vars.items():
        if isinstance(value, str):
            if value.startswith("parameter_store:"):
                param_name = value.split(":", 1)[1]
                param_value = ssm_store.get_parameter(param_name)
                if param_value is None:
                    raise ValueError(f"Parameter '{param_name}' not found in Parameter Store.")
                resolved_vars[var_name] = param_value
            elif value.startswith("gcp_secret_manager:"):
                secret_name = value.split(":", 1)[1]
                secret_value = gcp_secret_manager.access_secret_version(secret_name)
                if secret_value is None:
                    raise ValueError(f"Secret '{secret_name}' not found in GCP Secret Manager.")
                resolved_vars[var_name] = secret_value
            elif value.startswith("cloudformation_export:"):
                export_name = value.split(":", 1)[1]
                export_value = cf_exports.get_export_value(export_name)
                if export_value is None:
                    raise ValueError(f"Export '{export_name}' not found in CloudFormation exports.")
                resolved_vars[var_name] = export_value

    return resolved_vars


def get_all_envs(loc: str, file_path: str = "envars.yml") -> dict:
    """Loads and resolves variables for all environments in a given location."""
    manager = load_from_yaml(file_path)
    if loc is None:
        loc = get_default_location_name(manager)
        if loc is None:
            raise ValueError("Could not determine default location. Please specify with --loc.")
    all_envs = {}
    for env_name in manager.environments:
        all_envs[env_name] = _get_resolved_variables(manager, loc, env_name, decrypt=True)
    return all_envs


def get_env(env: str, loc: str, file_path: str = "envars.yml") -> dict:
    """Loads and resolves variables for a given environment and location."""
    manager = load_from_yaml(file_path)
    if loc is None:
        loc = get_default_location_name(manager)
        if loc is None:
            raise ValueError("Could not determine default location. Please specify with --loc.")
    return _get_resolved_variables(manager, loc, env, decrypt=True)


def _validate_variable_value(manager: VariableManager, var_name: str, value: str):
    """Validates a variable's value against its validation rule."""
    if var_name in manager.variables:
        variable = manager.variables[var_name]
        if variable.validation:
            import re

            if not re.match(variable.validation, value):
                raise ValueError(
                    f"Value '{value}' for variable '{var_name}' does not match validation regex: {variable.validation}"
                )
