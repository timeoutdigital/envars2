import os
import subprocess

import typer
import yaml
from rich.console import Console
from rich.tree import Tree

from src.envars.aws_kms import AWSKMSAgent
from src.envars.gcp_kms import GCPKMSAgent
from src.envars.main import Secret, load_from_yaml, write_envars_yml
from src.envars.models import Environment, Location, Variable, VariableManager, VariableValue

app = typer.Typer()
console = Console()
error_console = Console(stderr=True)


@app.command(name="init")
def init_envars(
    ctx: typer.Context,
    app_name: str = typer.Option(..., "--app", "-a", help="Application name."),
    env: str = typer.Option(..., "--env", "-e", help="Comma-separated list of environments."),
    loc: str = typer.Option(..., "--loc", "-l", help="Comma-separated list of locations in name:id format."),
    kms_key: str = typer.Option(None, "--kms-key", "-k", help="Global KMS key."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing envars.yml file."),
):
    """Initializes a new envars.yml file."""
    assert ctx.parent is not None
    file_path = ctx.parent.params["file_path"]

    if os.path.exists(file_path) and not force:
        error_console.print(f"[bold red]Error:[/] {file_path} already exists. Use --force to overwrite.")
        raise typer.Exit(code=1)

    manager = VariableManager(app=app_name, kms_key=kms_key)

    environments = [e.strip() for e in env.split(",")]
    for env_name in environments:
        manager.add_environment(Environment(name=env_name))

    locations = [l.strip() for l in loc.split(",")]
    for loc_item in locations:
        try:
            name, loc_id = loc_item.split(":", 1)
            manager.add_location(Location(name=name, location_id=loc_id))
        except ValueError as e:
            error_console.print(f"[bold red]Error:[/] Invalid location format: {loc_item}. Use name:id.")
            raise typer.Exit(code=1) from e

    try:
        write_envars_yml(manager, file_path)
        console.print(f"[bold green]Successfully initialized {file_path}[/]")
    except Exception as e:
        error_console.print(f"[bold red]Error writing to envars file:[/] {e}")
        raise typer.Exit(code=1) from e


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context, file_path: str = typer.Option("envars.yml", "--file", "-f", help="Path to the envars.yml file.")
):
    if ctx.invoked_subcommand is None:
        console.print("[bold green]Welcome to the Envars CLI![/]")
        console.print("Use 'print' to load and display an envars file.")
        return

    if ctx.invoked_subcommand == "init":
        return

    try:
        manager = load_from_yaml(file_path)
        ctx.obj = manager
    except FileNotFoundError as e:
        error_console.print(f"[bold red]Error:[/] {file_path} not found. Use 'init' to create a new file.")
        raise typer.Exit(code=1) from e
    except Exception as e:
        error_console.print(f"[bold red]Error loading envars file:[/] {e}")
        raise typer.Exit(code=1) from e


@app.command(name="add")
def add_env_var(
    ctx: typer.Context,
    var_assignment: str = typer.Argument(..., help="Variable assignment in VAR=value format."),
    env: str = typer.Option(None, "--env", "-e", help="Environment name."),
    loc: str = typer.Option(None, "--loc", "-l", help="Location name."),
    secret: bool = typer.Option(False, "--secret", "-s", help="Encrypt the variable value."),
):
    """Adds or updates an environment variable in the envars.yml file."""
    manager = ctx.obj
    assert ctx.parent is not None
    file_path = ctx.parent.params["file_path"]

    try:
        var_name, var_value = var_assignment.split("=", 1)
    except ValueError as e:
        error_console.print("[bold red]Error:[/bold red] Invalid variable assignment format. Use VAR=value.")
        raise typer.Exit(code=1) from e

    if var_name.upper() != var_name:
        error_console.print("[bold red]Error:[/] Variable names must be uppercase.")
        raise typer.Exit(code=1)

    # Ensure variable exists
    if var_name not in manager.variables:
        manager.add_variable(Variable(name=var_name))

    if secret:
        if not manager.kms_key:
            error_console.print("[bold red]Error:[/] Cannot encrypt without a kms_key in configuration.")
            raise typer.Exit(code=1)

        # Determine KMS provider
        if manager.kms_key.startswith("arn:aws:kms:"):
            agent = AWSKMSAgent()
            key_id = manager.kms_key
        elif manager.kms_key.startswith("projects/"):
            agent = GCPKMSAgent()
            key_id = manager.kms_key
        else:
            error_console.print(f"[bold red]Error:[/] Unknown KMS key format: {manager.kms_key}")
            raise typer.Exit(code=1)

        # Get encryption context
        encryption_context = {
            "app": manager.app or "",
        }
        if env:
            encryption_context["environment"] = env
        if loc:
            encryption_context["location"] = loc

        encrypted_value = agent.encrypt(var_value, key_id, encryption_context)
        var_value = Secret(encrypted_value)

    # Determine scope and create VariableValue
    scope_type = "DEFAULT"
    environment_name = None
    location_id = None

    if env and loc:
        scope_type = "SPECIFIC"
        environment_name = env
        # Find location_id by name
        found_loc = next((l for l in manager.locations.values() if l.name == loc), None)
        if not found_loc:
            error_console.print(f"[bold red]Error:[/bold red] Location '{loc}' not found.")
            raise typer.Exit(code=1)
        location_id = found_loc.location_id
    elif env:
        scope_type = "ENVIRONMENT"
        environment_name = env
    elif loc:
        scope_type = "LOCATION"
        # Find location_id by name
        found_loc = next((l for l in manager.locations.values() if l.name == loc), None)
        if not found_loc:
            error_console.print(f"[bold red]Error:[/bold red] Location '{loc}' not found.")
            raise typer.Exit(code=1)
        location_id = found_loc.location_id

    new_var_value = VariableValue(
        variable_name=var_name,
        value=var_value,
        scope_type=scope_type,
        environment_name=environment_name,
        location_id=location_id,
    )

    # Remove existing value if it matches the scope to allow update
    # This is a simplified update logic. A more robust solution might involve
    # finding the exact VariableValue to update or having a dedicated update method.
    existing_values = [vv for vv in manager.variable_values if vv.variable_name == var_name]
    for ev in existing_values:
        if ev.scope_type == new_var_value.scope_type:
            if new_var_value.scope_type == "DEFAULT":
                manager.variable_values.remove(ev)
                break
            elif new_var_value.scope_type == "ENVIRONMENT" and ev.environment_name == new_var_value.environment_name:
                manager.variable_values.remove(ev)
                break
            elif new_var_value.scope_type == "LOCATION" and ev.location_id == new_var_value.location_id:
                manager.variable_values.remove(ev)
                break
            elif (
                new_var_value.scope_type == "SPECIFIC"
                and ev.environment_name == new_var_value.environment_name
                and ev.location_id == new_var_value.location_id
            ):
                manager.variable_values.remove(ev)
                break

    manager.add_variable_value(new_var_value)

    try:
        write_envars_yml(manager, file_path)
        console.print(f"[bold green]Successfully added/updated {var_name} in {file_path}[/]")
    except Exception as e:
        error_console.print(f"[bold red]Error writing to envars file:[/] {e}")
        raise typer.Exit(code=1) from e


def _get_decrypted_value(manager: VariableManager, vv: VariableValue):
    """Helper function to decrypt a single VariableValue."""
    if not isinstance(vv.value, Secret):
        return vv.value

    if not manager.kms_key:
        error_console.print("[bold red]Error:[/] Cannot decrypt without a kms_key in configuration.")
        raise typer.Exit(code=1)

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
            error_console.print(f"[bold red]Error:[/] Unknown KMS key format: {manager.kms_key}")
            raise typer.Exit(code=1)
    except Exception as e:
        error_console.print(f"[bold red]Error decrypting {vv.variable_name}:[/] {e}")
        return "[DECRYPTION FAILED]"


@app.command(name="print")
def print_envars(
    ctx: typer.Context,
    env: str = typer.Option(None, "--env", "-e", help="Filter by environment."),
    loc: str = typer.Option(None, "--loc", "-l", help="Filter by location."),
    decrypt: bool = typer.Option(False, "--decrypt", "-d", help="Decrypt secret values."),
):
    """Prints the contents of the envars.yml file in a human-readable format."""
    manager = ctx.obj

    if env and env not in manager.environments:
        error_console.print(f"[bold red]Error:[/] Environment '{env}' not found in configuration.")
        raise typer.Exit(code=1)

    if loc and not any(l.name == loc for l in manager.locations.values()):
        error_console.print(f"[bold red]Error:[/] Location '{loc}' not found in configuration.")
        raise typer.Exit(code=1)

    # VAR=value format when both env and loc are specified
    if env and loc:
        for var_name in manager.variables:
            variable_value_obj = manager.get_variable(var_name, env, loc)
            if variable_value_obj:
                value = (
                    _get_decrypted_value(manager, variable_value_obj)
                    if decrypt and isinstance(variable_value_obj.value, Secret)
                    else variable_value_obj.value
                )
                console.print(f"{var_name}={value}")
        return

    # Tree view for other cases
    tree = Tree("[bold green]Envars Configuration[/]")
    if manager.app:
        tree.add(f"[bold blue]App:[/] {manager.app}")
    if manager.kms_key:
        tree.add(f"[bold blue]KMS Key:[/] {manager.kms_key}")

    env_tree = tree.add("[bold blue]Environments[/]")
    for env_name in manager.environments:
        env_tree.add(env_name)

    loc_tree = tree.add("[bold blue]Locations[/]")
    for location in manager.locations.values():
        loc_tree.add(f"{location.name} (id: {location.location_id})")

    var_tree = tree.add("[bold blue]Variables[/]")
    for var_name, var in manager.variables.items():
        v_tree = var_tree.add(f"[bold]{var_name}[/] - {var.description}")
        for vv in manager.variable_values:
            if vv.variable_name == var_name:
                value = _get_decrypted_value(manager, vv) if decrypt and isinstance(vv.value, Secret) else vv.value
                scope_str = f"Scope: {vv.scope_type}"
                if vv.environment_name:
                    scope_str += f", Env: {vv.environment_name}"
                if vv.location_id:
                    loc_name = next(
                        (l.name for l in manager.locations.values() if l.location_id == vv.location_id),
                        "Unknown",
                    )
                    scope_str += f", Loc: {loc_name}"
                v_tree.add(f"({scope_str}) [cyan]Value:[/] {value}")

    console.print(tree)


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
            error_console.print(
                "[bold red]Error:[/] The --env option is required if the STAGE environment variable is not set."
            )
            raise typer.Exit(code=1)

    if env not in manager.environments:
        error_console.print(f"[bold red]Error:[/] Environment '{env}' not found in configuration.")
        raise typer.Exit(code=1)

    if not any(l.name == loc for l in manager.locations.values()):
        error_console.print(f"[bold red]Error:[/] Location '{loc}' not found in configuration.")
        raise typer.Exit(code=1)

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
                raise typer.Exit(code=1)
            resolved_vars[var_name] = value
    return resolved_vars


@app.command(name="exec", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def exec_command(
    ctx: typer.Context,
    loc: str = typer.Option(..., "--loc", "-l", help="Location for context."),
    env: str | None = typer.Option(
        None, "--env", "-e", help="Environment for context. Defaults to the STAGE environment variable."
    ),
):
    """Populates the environment and executes a command."""
    manager = ctx.obj
    resolved_vars = _get_resolved_variables(manager, loc, env, decrypt=True)

    new_env = os.environ.copy()
    for k, v in resolved_vars.items():
        new_env[k] = str(v)

    command = ctx.args
    if not command:
        error_console.print("[bold red]Error:[/] No command provided.")
        raise typer.Exit(code=1)

    try:
        os.execvpe(command[0], command, new_env)
    except FileNotFoundError:
        error_console.print(f"[bold red]Error:[/] Command not found: {command[0]}")
        raise typer.Exit(code=1)
    except Exception as e:
        error_console.print(f"[bold red]Error executing command:[/] {e}")
        raise typer.Exit(code=1) from e


@app.command(name="yaml")
def yaml_command(
    ctx: typer.Context,
    loc: str = typer.Option(..., "--loc", "-l", help="Location for context."),
    env: str | None = typer.Option(
        None, "--env", "-e", help="Environment for context. Defaults to the STAGE environment variable."
    ),
):
    """Prints the environment variables as YAML."""
    manager = ctx.obj
    resolved_vars = _get_resolved_variables(manager, loc, env, decrypt=True)
    console.print(yaml.dump({"envars": resolved_vars}, sort_keys=False))


@app.command(name="set-systemd-env")
def set_systemd_env(
    ctx: typer.Context,
    loc: str = typer.Option(..., "--loc", "-l", help="Location for context."),
    env: str | None = typer.Option(
        None, "--env", "-e", help="Environment for context. Defaults to the STAGE environment variable."
    ),
    decrypt: bool = typer.Option(True, "--decrypt", "-d", help="Decrypt secret values."),
):
    """Sets the environment variables for a systemd user service."""
    manager = ctx.obj
    resolved_vars = _get_resolved_variables(manager, loc, env, decrypt)

    if not resolved_vars:
        console.print("No variables to set.")
        return

    command = ["systemctl", "--user", "set-environment"]
    command.extend([f"{k}={v}" for k, v in resolved_vars.items()])

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        console.print("[bold green]Successfully set systemd environment variables.[/]")
    except FileNotFoundError:
        error_console.print("[bold red]Error:[/] `systemctl` command not found.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        error_console.print(f"[bold red]Error setting systemd environment variables:[/] {e.stderr}")
        raise typer.Exit(code=1) from e


@app.command(name="validate")
def validate_command(
    ctx: typer.Context,
):
    """Validates the envars.yml file for logical consistency."""
    manager = ctx.obj
    errors = []

    # Check that all variable values correspond to a defined variable
    defined_variable_names = set(manager.variables.keys())
    for vv in manager.variable_values:
        if vv.variable_name not in defined_variable_names:
            errors.append(f"Variable '{vv.variable_name}' has values but is not defined as a top-level variable.")

    # Check that all variable names are uppercase
    for var_name in manager.variables:
        if var_name.upper() != var_name:
            errors.append(f"Variable name '{var_name}' must be uppercase.")

    if errors:
        error_console.print("[bold red]Validation failed with the following errors:[/]")
        for error in set(errors):
            error_console.print(f"- {error}")
        raise typer.Exit(code=1)

    console.print("[bold green]Validation successful![/]")


if __name__ == "__main__":
    app()
