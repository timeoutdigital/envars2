# src/mycli/main.py
"""This module contains the core logic for the 'mycli' application."""

import time

from rich.console import Console
from rich.progress import track

console = Console()


def greet_user(name: str) -> None:
    """Greets the user with a personalized message."""
    console.print(f"Hello, [bold green]{name}[/bold green]! Welcome to My CLI.")


def perform_task(steps: int = 10) -> None:
    """Simulates a task with a progress bar."""
    console.print(f"Starting a simulated task with [bold blue]{steps}[/bold blue] steps...")
    for _step in track(range(steps), description="Processing..."):
        time.sleep(0.2)  # Simulate work
    console.print("[bold green]Task completed![/bold green]")


def show_info(verbose: bool = False) -> None:
    """Displays information about the CLI."""
    console.print("[bold yellow]My CLI Information:[/bold yellow]")
    console.print("  Version: [cyan]0.1.0[/cyan]")
    console.print("  Author: [magenta]Your Name[/magenta]")
    if verbose:
        console.print("  This is a sample CLI project demonstrating uv, and typer.")
        console.print("  It includes basic commands and rich output.")
