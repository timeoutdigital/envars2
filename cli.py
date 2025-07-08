# cli.py
"""This is the main entry point for the 'mycli' command-line application.

It uses Typer to define commands and options.
"""

import typer
from rich.console import Console

# Import functions from your main application logic
from src.envars.main import greet_user, perform_task, show_info

# Initialize Typer app
app = typer.Typer(
    name="mycli",
    help="A modern example CLI built with Typer and UV.",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=True,
)

console = Console()

# Define a callback for the --version option
def version_callback(value: bool, ctx: typer.Context):
    """Prints the application version and exits if --version is used."""
    if value:
        # ctx.resilient_parsing is checked by Typer internally for callbacks
        console.print("[bold]My CLI Version:[/bold] [green]0.1.0[/green]")
        raise typer.Exit()

@app.command()
def hello(
    name: str = typer.Option(
        "World", "--name", "-n",
        help="The name to greet.",
        show_default=True
    )
):
    """Greets the specified name."""
    greet_user(name)

@app.command()
def task(
    steps: int = typer.Option(
        10, "--steps", "-s",
        min=1,
        max=100,
        help="Number of steps for the simulated task.",
        show_default=True
    )
):
    """Performs a simulated task with a progress bar."""
    perform_task(steps)

@app.command()
def info(
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Displays verbose information."
    )
):
    """Displays information about the CLI."""
    show_info(verbose)

@app.callback()
def main(
    ctx: typer.Context, # Keep ctx here for potential future global use
    version: bool = typer.Option(
        False, "--version", "-V",
        help="Show the application's version and exit.",
        is_eager=True,
        callback=version_callback # Use the new callback function
    ),
):
    """My CLI is a versatile command-line tool for various tasks."""
    pass

if __name__ == "__main__":
    app()
