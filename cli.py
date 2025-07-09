import typer
from rich.console import Console
from rich.tree import Tree

from src.envars.main import load_from_yaml

app = typer.Typer()
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """A CLI for managing environment variables."""
    if ctx.invoked_subcommand is None:
        console.print("[bold green]Welcome to the Envars CLI![/]")
        console.print("Use 'print' to load and display an envars file.")


@app.command(name="print")
def print_envars(
    file_path: str = typer.Argument("envars.yml", help="Path to the envars.yml file."),
    env: str = typer.Option(None, "--env", "-e", help="Filter by environment."),
    loc: str = typer.Option(None, "--loc", "-l", help="Filter by location."),
):
    """Prints the contents of the envars.yml file in a human-readable format."""
    try:
        manager = load_from_yaml(file_path)
    except Exception as e:
        console.print(f"[bold red]Error loading envars file:[/] {e}")
        raise typer.Exit(code=1)

    tree = Tree("[bold green]Envars Configuration[/]")

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
