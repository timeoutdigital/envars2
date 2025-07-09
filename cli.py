import typer
from rich.console import Console
from rich.tree import Tree

from src.envars.main import load_from_yaml, write_envars_yml
from src.envars.models import Variable, VariableValue

app = typer.Typer()
console = Console()
error_console = Console(stderr=True)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context, file_path: str = typer.Option("envars.yml", "--file", "-f", help="Path to the envars.yml file.")
):
    if ctx.invoked_subcommand is None:
        console.print("[bold green]Welcome to the Envars CLI![/]")
        console.print("Use 'print' to load and display an envars file.")
        return

    try:
        manager = load_from_yaml(file_path)
        ctx.obj = manager
    except Exception as e:
        error_console.print(f"[bold red]Error loading envars file:[/] {e}")
        raise typer.Exit(code=1)


@app.command(name="add")
def add_env_var(
    ctx: typer.Context,
    var_assignment: str = typer.Argument(..., help="Variable assignment in VAR=value format."),
    env: str = typer.Option(None, "--env", "-e", help="Environment name."),
    loc: str = typer.Option(None, "--loc", "-l", help="Location name."),
):
    """Adds or updates an environment variable in the envars.yml file."""
    manager = ctx.obj
    file_path = ctx.parent.params["file_path"]

    try:
        var_name, var_value = var_assignment.split("=", 1)
    except ValueError:
        error_console.print("[bold red]Error:[/bold red] Invalid variable assignment format. Use VAR=value.")
        raise typer.Exit(code=1)

    # Ensure variable exists
    if var_name not in manager.variables:
        manager.add_variable(Variable(name=var_name))

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
        raise typer.Exit(code=1)


@app.command(name="print")
def print_envars(
    ctx: typer.Context,
    env: str = typer.Option(None, "--env", "-e", help="Filter by environment."),
    loc: str = typer.Option(None, "--loc", "-l", help="Filter by location."),
):
    """Prints the contents of the envars.yml file in a human-readable format."""
    manager = ctx.obj
    tree = Tree("[bold green]Envars Configuration[/]")

    # App and KMS Key
    if manager.app:
        tree.add(f"[bold blue]App:[/] {manager.app}")
    if manager.kms_key:
        tree.add(f"[bold blue]KMS Key:[/] {manager.kms_key}")

    # Environments
    if not env and not loc:
        env_tree = tree.add("[bold blue]Environments[/]")
        for env_name in manager.environments:
            env_tree.add(env_name)

    # Locations
    if not env and not loc:
        loc_tree = tree.add("[bold blue]Locations[/]")
        for location in manager.locations.values():
            loc_tree.add(f"{location.name} (id: {location.location_id})")

    # Variables
    var_tree = tree.add("[bold blue]Variables[/]")
    for var_name, var in manager.variables.items():
        value = manager.get_variable_value(var_name, env, loc)
        if value:
            v_tree = var_tree.add(f"[bold]{var_name}[/] - {var.description}")
            v_tree.add(f"[cyan]Value:[/] {value}")

    console.print(tree)


if __name__ == "__main__":
    app()
