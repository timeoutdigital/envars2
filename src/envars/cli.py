import json
import os
import subprocess
import warnings

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from .cloud_utils import get_default_location_name
from .main import (
    PrettyDumper,
    Secret,
    _check_for_circular_dependencies,
    _get_decrypted_value,
    _get_resolved_variables,
    _validate_variable_value,
    load_from_yaml,
    write_envars_yml,
)
from .models import Environment as EnvarsEnvironment
from .models import Location, Variable, VariableManager, VariableValue

warnings.filterwarnings("ignore", "Your application has authenticated using end user credentials")


app = typer.Typer()
console = Console()
error_console = Console(stderr=True)


def _resolve_and_print_context(
    ctx: typer.Context, loc: str | None, env: str | None
) -> tuple[VariableManager, str | None, str | None]:
    """Resolves location and environment, printing debug info if verbose."""
    if env:
        os.environ["ENVARS_ENV"] = env
    manager = ctx.obj
    verbose = ctx.meta.get("verbose", False)

    resolved_loc = loc
    if resolved_loc is None:
        if not manager.locations:
            # No locations configured, so no need to resolve a default or error
            if verbose:
                console.print("[dim]DEBUG: No locations configured, proceeding without a specific location.[/dim]")
            resolved_loc = None  # Explicitly set to None
        else:
            # Locations are configured, try to auto-detect
            resolved_loc = get_default_location_name(manager)
            if resolved_loc is None:
                error_console.print(
                    "[bold red]Error:[/] Could not determine default location. Please specify with --loc."
                )
                raise typer.Exit(code=1)
            if verbose:
                console.print(f"[dim]DEBUG: Auto-detected location: '{resolved_loc}'[/dim]")
    else:
        # A location was explicitly provided, validate it
        if not any(l.name == resolved_loc for l in manager.locations.values()):
            error_console.print(f"[bold red]Error:[/] Location '{resolved_loc}' not found in configuration.")
            raise typer.Exit(code=1)
        if verbose:
            console.print(f"[dim]DEBUG: Using specified location: '{resolved_loc}'[/dim]")

    final_env = env
    if final_env is None:
        final_env = os.environ.get("ENVARS_ENV")
        if verbose and final_env is not None:
            console.print(f"[dim]DEBUG: Using environment from ENVARS_ENV: '{final_env}'[/dim]")
    elif verbose:
        console.print(f"[dim]DEBUG: Using specified environment: '{final_env}'[/dim]")

    return manager, resolved_loc, final_env


@app.command(name="init")
def init_envars(
    ctx: typer.Context,
    app_name: str = typer.Option(..., "--app", "-a", help="Application name."),
    env: str = typer.Option(..., "--env", "-e", help="Comma-separated list of environments."),
    loc: str = typer.Option("", "--loc", "-l", help="Comma-separated list of locations in name:id format."),
    kms_key: str = typer.Option(None, "--kms-key", "-k", help="Global KMS key."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing envars.yml file."),
    description_mandatory: bool = typer.Option(
        False, "--description-mandatory", help="Require descriptions for all variables."
    ),
):
    """Initializes a new envars.yml file."""
    assert ctx.parent is not None
    file_path = ctx.parent.params["file_path"]

    if os.path.exists(file_path) and not force:
        error_console.print(f"[bold red]Error:[/] {file_path} already exists. Use --force to overwrite.")
        raise typer.Exit(code=1)

    manager = VariableManager(app=app_name, kms_key=kms_key, description_mandatory=description_mandatory)

    environments = [e.strip() for e in env.split(",")]
    for env_name in environments:
        manager.add_environment(EnvarsEnvironment(name=env_name))

    if loc:
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


def _get_cloud_provider(manager: VariableManager) -> str | None:
    """Detects the cloud provider based on the KMS key."""
    if manager.kms_key:
        if manager.kms_key.startswith("arn:aws:kms:"):
            return "aws"
        if manager.kms_key.startswith("projects/"):
            return "gcp"
    return None


def _check_all_contexts_for_circular_dependencies(manager: VariableManager):
    """Checks all environment and location contexts for circular dependencies."""
    for env_name in manager.environments:
        for loc in manager.locations.values():
            # Mimic the variable resolution for a specific context
            resolved_vars = {}
            for var_name in manager.variables:
                variable_value_obj = manager.get_variable(var_name, env_name, loc.name)
                if variable_value_obj:
                    resolved_vars[var_name] = variable_value_obj.value

            # Now check for circular dependencies on this specific context
            try:
                _check_for_circular_dependencies(resolved_vars)
            except ValueError as e:
                # Re-raise with more context
                raise ValueError(
                    f"Circular dependency detected in context env='{env_name}', loc='{loc.name}': {e}"
                ) from e


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    file_path: str = typer.Option("envars.yml", "--file", "-f", help="Path to the envars.yml file."),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output, printing detected location and environment."
    ),
):
    if ctx.invoked_subcommand is None:
        welcome_message = (
            "[bold green]🚀 Welcome to Envars![/bold green]\n"
            "Your central hub for managing application configuration as code.\n\n"
            "✨ [bold]Discover commands:[/bold] `envars --help`\n"
            "🌱 [bold]Start a new project:[/bold] `envars init`"
        )
        panel = Panel(
            welcome_message,
            title="[bold cyan]Envars[/bold cyan]",
            subtitle="[italic]Application Config as Code[/italic]",
            border_style="blue",
            expand=False,
        )
        console.print(panel)
        return

    ctx.meta["verbose"] = verbose

    if ctx.invoked_subcommand == "init":
        return

    try:
        manager = load_from_yaml(file_path)
        manager.cloud_provider = _get_cloud_provider(manager)
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
    var_assignment: str = typer.Argument(None, help="Variable assignment in VAR=value format."),
    var_name: str = typer.Option(None, "--var-name", "-n", help="Variable name."),
    value_from_file: str = typer.Option(None, "--value-from-file", help="Read value from a file."),
    env: str = typer.Option(None, "--env", "-e", help="Environment name."),
    loc: str = typer.Option(None, "--loc", "-l", help="Location name."),
    secret: bool = typer.Option(False, "--secret", "-s", help="Encrypt the variable value."),
    no_secret: bool = typer.Option(False, "--no-secret", help="Store a sensitive variable as plaintext."),
    description: str = typer.Option(None, "--description", "-d", help="Description for the variable."),
    validation: str = typer.Option(None, "--validation", help="Regex pattern for value validation."),
):
    """Adds or updates an environment variable in the envars.yml file."""
    manager = ctx.obj
    assert ctx.parent is not None
    file_path = ctx.parent.params["file_path"]

    if var_assignment and (var_name or value_from_file):
        error_console.print("[bold red]Error:[/] Cannot use VAR=value argument with --var-name or --value-from-file.")
        raise typer.Exit(code=1)

    if not var_assignment and not (var_name and value_from_file):
        error_console.print(
            "[bold red]Error:[/] Either VAR=value argument or both --var-name and --value-from-file are required."
        )
        raise typer.Exit(code=1)

    if var_assignment:
        try:
            name, var_value = var_assignment.split("=", 1)
        except ValueError as e:
            error_console.print("[bold red]Error:[/bold red] Invalid variable assignment format. Use VAR=value.")
            raise typer.Exit(code=1) from e
        var_name = name
    elif var_name and value_from_file:
        try:
            with open(value_from_file) as f:
                var_value = f.read()
        except FileNotFoundError as e:
            error_console.print(f"[bold red]Error:[/] File not found: {value_from_file}")
            raise typer.Exit(code=1) from e
    else:
        # This case should be caught by the initial checks, but as a safeguard:
        error_console.print("[bold red]Error:[/] Invalid combination of arguments.")
        raise typer.Exit(code=1)

    if var_name.upper() != var_name:
        error_console.print("[bold red]Error:[/] Variable names must be uppercase.")
        raise typer.Exit(code=1)

    # Validate the value if a validation rule exists
    try:
        _validate_variable_value(manager, var_name, var_value)
    except ValueError as e:
        error_console.print(f"[bold red]Error:[/] {e}")
        raise typer.Exit(code=1) from e

    # Check for sensitive variable names
    sensitive_keywords = ["PASSWORD", "TOKEN", "SECRET", "KEY"]
    if any(keyword in var_name for keyword in sensitive_keywords) and not secret and not no_secret:
        error_console.print(
            f"[bold red]Error:[/] Variable '{var_name}' may be sensitive. "
            "Use --secret to encrypt or --no-secret to store as plaintext."
        )
        raise typer.Exit(code=1)

    # Validate remote variable prefix
    if manager.cloud_provider:
        if manager.cloud_provider == "aws" and var_value.startswith("gcp_secret_manager:"):
            error_console.print("[bold red]Error:[/] Cannot use 'gcp_secret_manager:' with an AWS KMS key.")
            raise typer.Exit(code=1)
        if manager.cloud_provider == "gcp" and (
            var_value.startswith("parameter_store:") or var_value.startswith("cloudformation_export:")
        ):
            error_console.print(
                "[bold red]Error:[/] Cannot use 'parameter_store:' or 'cloudformation_export:' with a GCP KMS key."
            )
            raise typer.Exit(code=1)

    # Ensure variable exists
    if var_name not in manager.variables:
        if manager.description_mandatory and not description:
            error_console.print(f"[bold red]Error:[/] Description is mandatory for new variable '{var_name}'.")
            raise typer.Exit(code=1)
        manager.add_variable(Variable(name=var_name, description=description, validation=validation))
    else:
        if description:
            manager.variables[var_name].description = description
        if validation:
            manager.variables[var_name].validation = validation

    if secret:
        if not env and not loc:
            error_console.print("[bold red]Error:[/] Secrets must be scoped to an environment and/or location.")
            raise typer.Exit(code=1)
        if not manager.kms_key:
            error_console.print("[bold red]Error:[/] Cannot encrypt without a kms_key in configuration.")
            raise typer.Exit(code=1)

        # Determine KMS provider
        if manager.kms_key.startswith("arn:aws:kms:"):
            from .aws_kms import AWSKMSAgent

            agent = AWSKMSAgent()
            key_id = manager.kms_key
        elif manager.kms_key.startswith("projects/"):
            from .gcp_kms import GCPKMSAgent

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
            encryption_context["env"] = env
        if loc:
            encryption_context["location"] = loc

        encrypted_value = agent.encrypt(var_value, key_id, encryption_context)
        var_value = Secret(encrypted_value)

    # Determine scope and create VariableValue
    scope_type = "DEFAULT"
    environment_name = None
    location_id = None

    if loc:
        if not manager.locations:
            error_console.print(
                "[bold red]Error:[/] 'locations' are not configured for use in the project. Cannot use '--loc'."
            )
            raise typer.Exit(code=1)
        found_loc = next((l for l in manager.locations.values() if l.name == loc), None)
        if not found_loc:
            error_console.print(f"[bold red]Error:[/bold red] Location '{loc}' not found.")
            raise typer.Exit(code=1)
        location_id = found_loc.location_id

    if env and loc:
        scope_type = "SPECIFIC"
        environment_name = env
    elif env:
        scope_type = "ENVIRONMENT"
        environment_name = env
    elif loc:
        scope_type = "LOCATION"

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

    # Check for circular dependencies in all contexts
    try:
        _check_all_contexts_for_circular_dependencies(manager)
    except ValueError as e:
        error_console.print(f"[bold red]Error:[/] {e}")
        raise typer.Exit(code=1) from e

    try:
        write_envars_yml(manager, file_path)
        console.print(f"[bold green]Successfully added/updated {var_name} in {file_path}[/]")
    except Exception as e:
        error_console.print(f"[bold red]Error writing to envars file:[/] {e}")
        raise typer.Exit(code=1) from e


@app.command(name="output")
def output_command(
    ctx: typer.Context,
    env: str | None = typer.Option(None, "--env", "-e", help="Filter by environment."),
    loc: str | None = typer.Option(None, "--loc", "-l", help="Filter by location."),
    format: str = typer.Option("dotenv", "--format", help="Output format (dotenv, yaml, json)."),
):
    """Prints the resolved variables for a given context."""
    manager, loc, env = _resolve_and_print_context(ctx, loc, env)

    try:
        resolved_vars = _get_resolved_variables(manager, loc, env, decrypt=True)
        if format == "dotenv":
            for k, v in resolved_vars.items():
                if "\n" in v:
                    # Escape newlines and wrap in quotes for dotenv format
                    escaped_v = v.replace("\n", "\\n")
                    print(f'{k}="{escaped_v}"')
                else:
                    print(f"{k}={v}")
        elif format == "yaml":
            print(yaml.dump({"envars": resolved_vars}, sort_keys=False, Dumper=PrettyDumper))
        elif format == "json":
            print(json.dumps({"envars": resolved_vars}, indent=2))
        else:
            error_console.print(f"[bold red]Error:[/] Invalid output format: {format}")
            raise typer.Exit(code=1)
    except ValueError as e:
        error_console.print(f"[bold red]Error:[/] {e}")
        raise typer.Exit(code=1) from e


@app.command(name="tree")
def tree_command(
    ctx: typer.Context,
    decrypt: bool = typer.Option(False, "--decrypt", "-d", help="Decrypt secret values."),
    truncate: int = typer.Option(
        20, "--truncate", "-t", help="Length to truncate secret values to. Use 0 to disable truncation."
    ),
):
    """Prints the contents of the envars.yml file in a tree view."""
    manager = ctx.obj
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
                try:
                    value = _get_decrypted_value(manager, vv) if decrypt and isinstance(vv.value, Secret) else vv.value
                except ValueError as e:
                    value = f"[DECRYPTION FAILED: {e}]"

                display_value = value
                is_secret = isinstance(vv.value, Secret)
                label = "Value:"
                if is_secret and not decrypt:
                    if truncate > 0:
                        display_value = f"{str(value)[:truncate]}..."
                    display_value = f"[bold yellow]{display_value}[/]"
                    label = "Encrypted Value:"

                scope_str = f"Scope: {vv.scope_type}"
                if vv.environment_name:
                    scope_str += f", Env: {vv.environment_name}"
                if vv.location_id:
                    loc_name = next(
                        (l.name for l in manager.locations.values() if l.location_id == vv.location_id),
                        "Unknown",
                    )
                    scope_str += f", Loc: {loc_name}"
                v_tree.add(f"({scope_str}) [cyan]{label}[/] {display_value}")

    console.print(tree)


@app.command(name="exec", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def exec_command(
    ctx: typer.Context,
    loc: str | None = typer.Option(None, "--loc", "-l", help="Location for context."),
    env: str | None = typer.Option(
        None, "--env", "-e", help="Environment for context. Defaults to the ENVARS_ENV environment variable."
    ),
):
    """Execute a command with the environment populated from the specified context.

    This command resolves variables based on the provided --env and --loc,
    populates the current shell's environment with these variables, and then
    executes the specified command. Secrets are automatically decrypted.

    Use '--' to separate the options for this command from the command you want to execute.

    Example:
      envars2 exec --env dev --loc aws -- my_script.py --some-arg
    """
    manager, loc, env = _resolve_and_print_context(ctx, loc, env)
    try:
        resolved_vars = _get_resolved_variables(manager, loc, env, decrypt=True)
    except ValueError as e:
        error_console.print(f"[bold red]Error:[/] {e}")
        raise typer.Exit(code=1) from e

    new_env = os.environ.copy()
    for k, v in resolved_vars.items():
        new_env[k] = str(v)

    command = ctx.args
    if not command:
        error_console.print("[bold red]Error:[/] No command provided.")
        raise typer.Exit(code=1)

    try:
        os.execvpe(command[0], command, new_env)  # noqa: S606
    except FileNotFoundError as e:
        error_console.print(f"[bold red]Error:[/] Command not found: {command[0]}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        error_console.print(f"[bold red]Error executing command:[/] {e}")
        raise typer.Exit(code=1) from e


@app.command(name="set-systemd-env")
def set_systemd_env(
    ctx: typer.Context,
    loc: str | None = typer.Option(None, "--loc", "-l", help="Location for context."),
    env: str | None = typer.Option(
        None, "--env", "-e", help="Environment for context. Defaults to the ENVARS_ENV environment variable."
    ),
    decrypt: bool = typer.Option(True, "--decrypt", "-d", help="Decrypt secret values."),
):
    """Sets the environment variables for a systemd user service."""
    manager, loc, env = _resolve_and_print_context(ctx, loc, env)
    try:
        resolved_vars = _get_resolved_variables(manager, loc, env, decrypt)
    except ValueError as e:
        error_console.print(f"[bold red]Error:[/] {e}")
        raise typer.Exit(code=1) from e

    if not resolved_vars:
        console.print("No variables to set.")
        return

    command = ["systemctl", "--user", "set-environment"]
    command.extend([f"{k}={v}" for k, v in resolved_vars.items()])

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)  # noqa: S603
        console.print("[bold green]Successfully set systemd environment variables.[/]")
    except FileNotFoundError as e:
        error_console.print("[bold red]Error:[/] `systemctl` command not found.")
        raise typer.Exit(code=1) from e
    except subprocess.CalledProcessError as e:
        error_console.print(f"[bold red]Error setting systemd environment variables:[/] {e.stderr}")
        raise typer.Exit(code=1) from e


@app.command(name="config")
def config_command(
    ctx: typer.Context,
    kms_key: str = typer.Option(None, "--kms-key", "-k", help="Global KMS key."),
    add_env: str = typer.Option(None, "--add-env", help="Add a new environment."),
    remove_env: str = typer.Option(None, "--remove-env", help="Remove an environment."),
    add_loc: str = typer.Option(None, "--add-loc", help="Add a new location in name:id format."),
    remove_loc: str = typer.Option(None, "--remove-loc", help="Remove a location by name."),
    description_mandatory: bool = typer.Option(
        None,
        "--description-mandatory/--no-description-mandatory",
        help="Require descriptions for all variables.",
    ),
):
    """Updates the configuration in the envars.yml file."""
    no_options_provided = all(
        v is None for v in [kms_key, add_env, remove_env, add_loc, remove_loc, description_mandatory]
    )
    if no_options_provided:
        console.print(ctx.get_help())
        raise typer.Exit()

    manager = ctx.obj
    assert ctx.parent is not None
    file_path = ctx.parent.params["file_path"]

    if kms_key:
        manager.kms_key = kms_key
    if add_env:
        manager.add_environment(EnvarsEnvironment(name=add_env))
    if remove_env:
        # Check if the environment is in use
        vars_using_env = [vv.variable_name for vv in manager.variable_values if vv.environment_name == remove_env]
        if vars_using_env:
            error_console.print(
                f"[bold red]Error:[/] Cannot remove environment '{remove_env}' because it is in use by the following variables: {', '.join(sorted(set(vars_using_env)))}"  # NOQA E501
            )
            raise typer.Exit(code=1)

        if remove_env in manager.environments:
            del manager.environments[remove_env]
    if add_loc:
        try:
            name, loc_id = add_loc.split(":", 1)
            manager.add_location(Location(name=name, location_id=loc_id))
        except ValueError as e:
            error_console.print(f"[bold red]Error:[/] Invalid location format: {add_loc}. Use name:id.")
            raise typer.Exit(code=1) from e
    if remove_loc:
        loc_to_remove = next((loc for loc in manager.locations.values() if loc.name == remove_loc), None)
        if loc_to_remove:
            # Check if the location is in use
            vars_using_loc = [
                vv.variable_name for vv in manager.variable_values if vv.location_id == loc_to_remove.location_id
            ]
            if vars_using_loc:
                error_console.print(
                    f"[bold red]Error:[/] Cannot remove location '{remove_loc}' because it is in use by the following variables: {', '.join(sorted(set(vars_using_loc)))}"  # NOQA E501
                )
                raise typer.Exit(code=1)
            del manager.locations[loc_to_remove.location_id]
    if description_mandatory is not None:
        manager.description_mandatory = description_mandatory

    try:
        write_envars_yml(manager, file_path)
        console.print("[bold green]Successfully updated configuration.[/]")
    except Exception as e:
        error_console.print(f"[bold red]Error writing to envars file:[/] {e}")
        raise typer.Exit(code=1) from e


@app.command(name="rotate-kms-key")
def rotate_kms_key(
    ctx: typer.Context,
    new_kms_key: str = typer.Option(..., "--new-kms-key", help="The new KMS key to use for encryption."),
    output_file: str = typer.Option("envars.new.yml", "--output-file", help="The name of the new envars.yml file."),
):
    """Rotates the KMS key and re-encrypts all secrets."""
    manager = ctx.obj
    new_manager = VariableManager(
        app=manager.app,
        kms_key=new_kms_key,
        description_mandatory=manager.description_mandatory,
    )

    for env in manager.environments.values():
        new_manager.add_environment(env)
    for loc in manager.locations.values():
        new_manager.add_location(loc)
    for var in manager.variables.values():
        new_manager.add_variable(var)

    for vv in manager.variable_values:
        if isinstance(vv.value, Secret):
            try:
                decrypted_value = _get_decrypted_value(manager, vv)
            except ValueError as e:
                error_console.print(f"[bold red]Error:[/] Failed to decrypt '{vv.variable_name}'. Aborting. {e}")
                raise typer.Exit(code=1) from e

            # Re-encrypt with the new key
            new_manager.kms_key = new_kms_key
            encryption_context = {
                "app": new_manager.app or "",
            }
            if vv.environment_name:
                encryption_context["env"] = vv.environment_name
            if vv.location_id:
                loc_name = next(
                    (l.name for l in new_manager.locations.values() if l.location_id == vv.location_id), None
                )
                if loc_name:
                    encryption_context["location"] = loc_name

            if new_kms_key.startswith("arn:aws:kms:"):
                from .aws_kms import AWSKMSAgent

                agent = AWSKMSAgent()
                encrypted_value = agent.encrypt(decrypted_value, new_kms_key, encryption_context)
            elif new_kms_key.startswith("projects/"):
                from .gcp_kms import GCPKMSAgent

                agent = GCPKMSAgent()
                encrypted_value = agent.encrypt(decrypted_value, new_kms_key, encryption_context)
            else:
                error_console.print(f"[bold red]Error:[/] Unknown KMS key format: {new_kms_key}")
                raise typer.Exit(code=1)

            new_var_value = VariableValue(
                variable_name=vv.variable_name,
                value=Secret(encrypted_value),
                scope_type=vv.scope_type,
                environment_name=vv.environment_name,
                location_id=vv.location_id,
            )
            new_manager.add_variable_value(new_var_value)
        else:
            new_manager.add_variable_value(vv)

    try:
        write_envars_yml(new_manager, output_file)
        console.print(f"[bold green]Successfully rotated KMS key and wrote new configuration to {output_file}[/]")
    except Exception as e:
        error_console.print(f"[bold red]Error writing to new envars file:[/] {e}")
        raise typer.Exit(code=1) from e


@app.command(name="validate")
def validate_command(
    ctx: typer.Context,
    ignore_default_secrets: bool = typer.Option(
        False, "--ignore-default-secrets", help="Ignore default secrets during validation."
    ),
):
    """Validates the envars.yml file for logical consistency."""
    manager = ctx.obj
    verbose = ctx.meta.get("verbose", False)
    errors = []

    if verbose:
        console.print("[dim]DEBUG: Running validation checks...[/dim]")

    # Check 1: All variable values correspond to a defined variable
    value_errors = []
    defined_variable_names = set(manager.variables.keys())
    for vv in manager.variable_values:
        if vv.variable_name not in defined_variable_names:
            value_errors.append(f"Variable '{vv.variable_name}' has values but is not defined as a top-level variable.")
    if not value_errors:
        if verbose:
            console.print("[dim]DEBUG: [PASS] All variable values have a corresponding definition.[/dim]")
    else:
        errors.extend(value_errors)

    # Check 2: All variable names are uppercase
    case_errors = []
    for var_name in manager.variables:
        if var_name.upper() != var_name:
            case_errors.append(f"Variable name '{var_name}' must be uppercase.")
    if not case_errors:
        if verbose:
            console.print("[dim]DEBUG: [PASS] All variable names are uppercase.[/dim]")
    else:
        errors.extend(case_errors)

    # Check 3: Missing descriptions if mandatory
    if manager.description_mandatory:
        desc_errors = []
        for var_name, var in manager.variables.items():
            if not var.description:
                desc_errors.append(f"Variable '{var_name}' is missing a description.")
        if not desc_errors:
            if verbose:
                console.print("[dim]DEBUG: [PASS] All mandatory descriptions are present.[/dim]")
        else:
            errors.extend(desc_errors)
    elif verbose:
        console.print("[dim]DEBUG: [SKIP] Description mandatory check is disabled.[/dim]")

    # Check 4: Default secrets
    if not ignore_default_secrets:
        secret_errors = []
        for vv in manager.variable_values:
            if isinstance(vv.value, Secret) and vv.scope_type == "DEFAULT":
                secret_errors.append(f"Variable '{vv.variable_name}' is a secret and cannot have a default value.")
        if not secret_errors:
            if verbose:
                console.print("[dim]DEBUG: [PASS] No default secrets found.[/dim]")
        else:
            errors.extend(secret_errors)
    elif verbose:
        console.print("[dim]DEBUG: [SKIP] Default secret check is ignored.[/dim]")

    # Check 5: Mismatched remote variables
    if manager.cloud_provider:
        remote_errors = []
        for vv in manager.variable_values:
            if isinstance(vv.value, str):
                if manager.cloud_provider == "aws" and vv.value.startswith("gcp_secret_manager:"):
                    remote_errors.append(
                        f"Variable '{vv.variable_name}' uses 'gcp_secret_manager:' with an AWS KMS key."
                    )
                if manager.cloud_provider == "gcp" and (
                    vv.value.startswith("parameter_store:") or vv.value.startswith("cloudformation_export:")
                ):
                    remote_errors.append(
                        f"Variable '{vv.variable_name}' uses 'parameter_store:' or 'cloudformation_export:' with a GCP"
                        " KMS key."
                    )
        if not remote_errors:
            if verbose:
                console.print("[dim]DEBUG: [PASS] No mismatched remote variables found.[/dim]")
        else:
            errors.extend(remote_errors)
    elif verbose:
        console.print("[dim]DEBUG: [SKIP] Remote variable check (no cloud provider configured).[/dim]")

    # Check 6: Circular dependencies
    all_vars = {vv.variable_name: vv.value for vv in manager.variable_values}
    try:
        _check_for_circular_dependencies(all_vars)
        if verbose:
            console.print("[dim]DEBUG: [PASS] No circular dependencies detected.[/dim]")
    except ValueError as e:
        errors.append(str(e))

    # Check 7: All variable values match their validation rules
    validation_errors = []
    for vv in manager.variable_values:
        try:
            _validate_variable_value(manager, vv.variable_name, str(vv.value))
        except ValueError as e:
            validation_errors.append(str(e))
    if not validation_errors:
        if verbose:
            console.print("[dim]DEBUG: [PASS] All variable values passed validation rules.[/dim]")
    else:
        errors.extend(validation_errors)

    if errors:
        error_console.print("[bold red]Validation failed with the following errors:[/]")
        for error in set(errors):
            error_console.print(f"- {error}")
        raise typer.Exit(code=1)

    console.print("[bold green]Validation successful![/]")


if __name__ == "__main__":
    app()
